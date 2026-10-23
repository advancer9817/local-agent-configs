"""hindsight-memory Hermes plugin.

Default long-term memory backend for Hermes, replacing mcore-memory.

pre_llm_call:
  - Query Hindsight `recall` with the user_message, inject the result as context.
post_llm_call:
  - Async `retain` the just-finished Q/A turn as a document (Hindsight extracts facts server-side).
on_session_end:
  - Fallback: run hindsight-ingest.py to retain the whole state.db transcript
    (captures turns missed by post_llm_call on interrupt / compression).

Endpoint is the authenticated public Hindsight MCP (Bearer token read from
~/.hermes/.hindsight-token). All failures are swallowed; memory must never
block the conversation.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HINDSIGHT_URL = os.environ.get(
    "HINDSIGHT_MCP_URL",
    "http://35.236.134.50:18888/mcp/mcore-active-snapshot/",
)
TOKEN_FILE = Path(os.environ.get("HINDSIGHT_TOKEN_FILE", str(Path.home() / ".hermes" / ".hindsight-token")))
TIMEOUT = 8
RECALL_BUDGET_TOKENS = 1500
AGENT_ID = "hermes"
MIN_QUERY_LEN = 4

# Session-end fallback: reuse agent-hooks/hindsight-ingest.py (reads state.db transcript)
HINDSIGHT_INGEST_SCRIPT = Path.home() / ".hermes" / "agent-hooks" / "hindsight-ingest.py"


def _token() -> str:
    if os.environ.get("HINDSIGHT_TOKEN"):
        return os.environ["HINDSIGHT_TOKEN"]
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _no_proxy_opener():
    # Hindsight is a direct public IP; never route through Clash/HTTP proxy.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _headers(session_id: str = "") -> dict:
    h = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    tok = _token()
    if tok:
        h["Authorization"] = "Bearer " + tok
    if session_id:
        h["Mcp-Session-Id"] = session_id
    return h


def _mcp_session() -> str:
    req = urllib.request.Request(
        HINDSIGHT_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "hermes-hindsight-plugin", "version": "1.0"},
            },
        }).encode(),
        headers=_headers(),
        method="POST",
    )
    with _no_proxy_opener().open(req, timeout=TIMEOUT) as resp:
        return resp.headers.get("Mcp-Session-Id", "")


def _mcp_call(session_id: str, tool: str, args: dict, timeout: float = TIMEOUT) -> dict:
    req = urllib.request.Request(
        HINDSIGHT_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }, ensure_ascii=False).encode(),
        headers=_headers(session_id),
        method="POST",
    )
    with _no_proxy_opener().open(req, timeout=timeout) as resp:
        body = resp.read().decode()
        raw = body.strip()
        for line in body.splitlines():
            if line.startswith("data:"):
                raw = line[5:].strip()
                break
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
    return {}


def _extract_text(result: dict) -> str:
    content = result.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            return item["text"]
    return ""


def _format_recall(raw_text: str) -> str:
    """Turn Hindsight recall JSON into a compact readable context block."""
    if not raw_text or not raw_text.strip():
        return ""
    try:
        data = json.loads(raw_text)
    except Exception:
        return raw_text.strip()
    # Prefer a server-provided context field if any.
    if isinstance(data, dict):
        ctx = data.get("context") or data.get("text")
        if isinstance(ctx, str) and ctx.strip():
            return ctx.strip()
        results = data.get("results") or data.get("memories") or []
        lines = []
        if isinstance(results, list):
            for m in results:
                if isinstance(m, dict):
                    t = m.get("text") or m.get("content") or m.get("memory") or ""
                    if t:
                        lines.append("- " + str(t).strip())
        if lines:
            return "\n".join(lines)
    return raw_text.strip()


def _query_memory(query: str) -> str:
    """Query Hindsight recall; return a formatted context string, '' on failure."""
    try:
        sid = _mcp_session()
        result = _mcp_call(sid, "recall", {
            "query": query,
            "max_tokens": RECALL_BUDGET_TOKENS,
            "budget": "mid",
        })
        return _format_recall(_extract_text(result))
    except urllib.error.URLError:
        logger.debug("hindsight-memory: 服务不可用，跳过记忆查询")
        return ""
    except Exception as exc:
        logger.debug("hindsight-memory: 查询失败 %s", exc)
        return ""


def _retain_async(user_message: str, assistant_response: str) -> None:
    """Background: retain the current Q/A turn as a document into Hindsight."""
    document = (
        f"User: {user_message[:2000]}\n"
        f"Assistant: {assistant_response[:2000]}"
    )
    try:
        sid = _mcp_session()
        result = _mcp_call(sid, "retain", {
            "content": document,
            "context": f"session-{AGENT_ID}",
            "tags": [f"agent:{AGENT_ID}", "source:turn"],
        }, timeout=30)
        logger.info("hindsight-memory: retain result %s", str(result)[:200])
    except Exception as exc:
        logger.warning("hindsight-memory: retain 失败 %s", exc)


# ---------------------------------------------------------------------------
# Hook handlers
# ---------------------------------------------------------------------------

def _on_pre_llm_call(**kwargs: Any):
    user_message: str = kwargs.get("user_message", "") or ""
    if len(user_message.strip()) < MIN_QUERY_LEN:
        return None
    memory_ctx = _query_memory(user_message)
    if not memory_ctx:
        return None
    return {"context": f"\n---\n[Hindsight 记忆]\n{memory_ctx}\n---\n"}


def _on_post_llm_call(**kwargs: Any):
    user_message: str = kwargs.get("user_message", "") or ""
    assistant_response: str = kwargs.get("assistant_response", "") or ""
    if not user_message.strip() or not assistant_response.strip():
        return
    t = threading.Thread(
        target=_retain_async,
        args=(user_message, assistant_response),
        daemon=True,
        name="hindsight-retain",
    )
    t.start()


def _on_session_end(**kwargs: Any):
    """Session-end fallback: retain the whole transcript via hindsight-ingest.py."""
    script_path = HINDSIGHT_INGEST_SCRIPT
    if not script_path.exists():
        return
    session_id: str = kwargs.get("session_id", "") or ""
    payload = {"session_id": session_id} if session_id else {}

    def _run() -> None:
        try:
            subprocess.run(
                [sys.executable or "python3", str(script_path), "--agent", AGENT_ID],
                input=json.dumps(payload).encode(),
                capture_output=True,
                timeout=120,
            )
        except Exception as exc:
            logger.debug("hindsight-memory: session-end retain 失败 %s", exc)

    t = threading.Thread(target=_run, daemon=True, name="hindsight-session-end")
    t.start()


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
    logger.info("hindsight-memory plugin registered (pre_llm_call + post_llm_call + on_session_end)")
