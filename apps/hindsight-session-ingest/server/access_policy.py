"""Map a request to (banks, needed permission). Unknown shapes are admin-only (fail closed)."""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, unquote

ADMIN = "admin"
PUBLIC = "public"
READ_TOOLS = re.compile(r"^(recall|reflect|list_(?!banks)\w+|get_\w+|search_\w+)$")
MANAGE_TOOLS = {"update_bank", "delete_bank", "clear_memories", "create_bank", "list_banks"}
READ_POSTS = re.compile(r"/(memories/recall|reflect|prompts/preview|memories/dry-run-extract|"
                        r"consolidation-strategies/preview|mental-models/[^/]+/dry-run-refresh)$")
# Bank-wide settings, membership-like objects and bulk moves of a bank's data.
MANAGE_SUFFIX = re.compile(r"^(|/config|/profile|/background|/aliases(/.*)?|/webhooks(/.*)?|/import|/clone|"
                           r"/transfer/.*|/document-transfer(/.*)?|/export|/consolidation/recover|/observations)$")


class Decision:
    def __init__(self, banks=(), level="read", kind="bank", filter_list=False):
        self.banks, self.level, self.kind, self.filter_list = list(banks), level, kind, filter_list

    def __repr__(self):
        return f"Decision({self.kind}, {self.banks}, {self.level})"


def method_level(method, rest):
    if method in ("GET", "HEAD", "OPTIONS"):
        return "read"
    if method == "POST" and READ_POSTS.search(rest):
        return "read"
    if MANAGE_SUFFIX.match(rest) and not (method == "POST" and rest == ""):
        return "manage"
    if method == "DELETE" and rest == "/memories":
        return "manage"
    return "write"


def mcp_level(body):
    """Classify a JSON-RPC body by the tools it calls; batches take the strongest level."""
    try:
        message = json.loads(body or b"{}")
    except ValueError:
        return "manage"
    level = "read"
    for item in message if isinstance(message, list) else [message]:
        if not isinstance(item, dict) or item.get("method") != "tools/call":
            continue
        name = str((item.get("params") or {}).get("name") or "")
        if name in MANAGE_TOOLS:
            return "manage"
        if not READ_TOOLS.match(name):
            level = "write"
    return level


def chunk_bank(chunk_id, grants):
    """Chunk ids are '<bank>_<document>_<index>'; banks may contain '_', so match known grants."""
    return [bank for bank in grants if chunk_id.startswith(bank + "_")]


def storage_bank(key):
    parts = [unquote(part) for part in key.split("/")]
    for index, part in enumerate(parts[:-1]):
        if part == "banks" and parts[index + 1]:
            return parts[index + 1]
    return None


def api_decision(method, path, body=b"", grants=()):
    """Hindsight API port: /v1, /mcp, /ext."""
    if path in ("/health", "/v1/version", "/v1/bank-template-schema"):
        return Decision(kind=PUBLIC)
    if path.rstrip("/") == "/v1/default/banks":
        return Decision(kind=PUBLIC, filter_list=True) if method == "GET" else Decision(kind=ADMIN, level="manage")
    match = re.match(r"^/v1/default/banks/([^/]+)(/.*)?$", path)
    if match:
        bank, rest = unquote(match.group(1)), match.group(2) or ""
        return Decision([bank], method_level(method, rest))
    match = re.match(r"^/v1/default/chunks/(.+)$", path)
    if match and method == "GET":
        banks = chunk_bank(unquote(match.group(1)), grants)
        return Decision(banks[:1], "read") if banks else Decision(kind=ADMIN, level="read")
    match = re.match(r"^/v1/default/files/download/(.+)$", path)
    if match and method == "GET":
        bank = storage_bank(match.group(1))
        return Decision([bank], "read") if bank else Decision(kind=ADMIN, level="read")
    match = re.match(r"^/mcp/([^/]+)(/.*)?$", path)
    if match:
        return Decision([unquote(match.group(1))], mcp_level(body) if method == "POST" else "read")
    match = re.match(r"^/ext/ingest/banks/([^/]+)(/.*)?$", path)
    if match:
        return Decision([unquote(match.group(1))], "read" if method == "GET" else "write")
    # Multi-bank MCP root, metrics, docs and anything new: administrators only.
    return Decision(kind=ADMIN, level="read" if method == "GET" else "manage")


def multipart_bank(body):
    match = re.search(rb'name="request"\r\n(?:[^\r\n]+\r\n)*\r\n(.*?)\r\n--', body or b"", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1)).get("bank_id")
    except (ValueError, AttributeError):
        return None


def console_decision(method, path, query="", body=b"", content_type="", grants=()):
    """Native control plane behind the console login: pages and its /api routes."""
    if path.startswith("/_next/") or path in ("/favicon.ico", "/api/health", "/api/version") \
            or re.match(r"^/[\w.-]+\.(png|svg|ico|webmanifest|txt)$", path):
        return Decision(kind=PUBLIC)
    if path.startswith("/api/auth/"):
        return Decision(kind=ADMIN, level="manage")
    params = parse_qs(query)
    match = re.match(r"^/(?:[\w-]+/)?banks/([^/]+)", path)
    if not path.startswith("/api/") and match:
        return Decision([unquote(match.group(1))], "read")
    if not path.startswith("/api/"):
        return Decision(kind=PUBLIC)
    if path.rstrip("/") == "/api/banks":
        return Decision(kind=PUBLIC, filter_list=True) if method == "GET" else Decision(kind=ADMIN, level="manage")
    match = re.match(r"^/api/banks/([^/]+)(/.*)?$", path)
    if match:
        return Decision([unquote(match.group(1))], method_level(method, match.group(2) or ""))
    match = re.match(r"^/api/(operations|stats)/([^/]+)", path)
    if match:
        return Decision([unquote(match.group(2))], "read" if method == "GET" else "write")
    if path == "/api/chunks" and params.get("chunk_id"):
        banks = chunk_bank(params["chunk_id"][0], grants)
        return Decision(banks[:1], "read") if banks else Decision(kind=ADMIN, level="read")
    if path == "/api/files/download" and params.get("path"):
        bank = storage_bank(params["path"][0])
        return Decision([bank], "read") if bank else Decision(kind=ADMIN, level="read")
    bank = (params.get("bank_id") or params.get("agent_id") or [None])[0]
    if bank is None and body:
        if "multipart/form-data" in content_type:
            bank = multipart_bank(body)
        else:
            try:
                data = json.loads(body)
                bank = data.get("bank_id") or data.get("agent_id") if isinstance(data, dict) else None
            except ValueError:
                bank = None
    if not bank:
        return Decision(kind=ADMIN, level="read" if method == "GET" else "manage")
    if method == "GET" or path in ("/api/recall", "/api/reflect"):
        level = "read"
    elif path.startswith("/api/documents/transfer") or path.startswith("/api/knowledge-base/export"):
        level = "manage"
    else:
        level = "write"
    return Decision([str(bank)], level)


def filter_banks(payload, principal):
    """Keep only banks the principal may read; works for {'banks': [...]} and bare lists."""
    def keep(item):
        bank = item.get("bank_id") or item.get("id") if isinstance(item, dict) else item
        return isinstance(bank, str) and principal.visible(bank)
    if isinstance(payload, dict) and isinstance(payload.get("banks"), list):
        payload = dict(payload, banks=[item for item in payload["banks"] if keep(item)])
        if "total" in payload:
            payload["total"] = len(payload["banks"])
        return payload
    if isinstance(payload, list):
        return [item for item in payload if keep(item)]
    return payload
