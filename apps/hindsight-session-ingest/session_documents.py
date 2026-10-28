"""Portable session metadata and explicitly linked document ingestion."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile

from ingest_safety import artifact_identity, inspect_upload

SCHEMA_VERSION = 6
CONVERTED_SUFFIXES = {".html", ".htm", ".csv", ".pdf", ".docx", ".pptx", ".xlsx"}
MAX_BYTES = 1_000_000
# Converted formats are parsed on the server; only upload safety runs locally.
MAX_CONVERTED_BYTES = 20_000_000
MAX_UPLOADS_PER_TURN = 3
DOCUMENT_SUFFIXES = {".md", ".txt", ".rst", ".csv", ".json", ".html", ".htm", ".pdf", ".docx", ".pptx", ".xlsx"}
PRIVATE_COMPONENTS = {".ssh", ".aws", ".azure", ".gnupg", ".git", "node_modules", "venv", ".venv"}
PRIVATE_NAME = re.compile(r"(?:^|[-_.])(auth|credentials?|secrets?|tokens?|passwords?|connection|runtime|config|settings|private|backup|before)(?:[-_.]|$)", re.I)
ROLE = re.compile(r"(?:^|\n\n)(user|assistant):\s*")


def now():
    return datetime.now(timezone.utc).isoformat()


def redact(text):
    """Mask bearer tokens, API keys and secret assignments; shared by client and server."""
    text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
                  "[REDACTED PRIVATE KEY]", text, flags=re.S)
    text = re.sub(r'(?i)Bearer\s+[A-Za-z0-9_./+=-]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'\b(?:sk-|ghp_|github_pat_|gsk_)[A-Za-z0-9_-]{12,}', '[REDACTED]', text)
    pattern = r'''(?im)((?<!\w)["']?(?:api[_-]?key|(?:auth|access|refresh|mcp)[_-]?token|token|password|secret)["']?\s*[=:]\s*)("[^"\r\n]*"|'[^'\r\n]*'|[^\s,;}]+)'''

    def replace(match):
        value = match.group(2)
        quote = value[0] if value[0] in "\"'" else ""
        return match.group(1) + quote + "[REDACTED]" + quote
    return re.sub(pattern, replace, text)


def save_state(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if os.name != "nt":
                os.fchmod(handle.fileno(), 0o600)
            json.dump(value, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_state(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class SessionLock:
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.handle = self.path.open("a+b")
        if os.name == "nt":
            import msvcrt
            self.handle.write(b"0")
            self.handle.flush()
            self.handle.seek(0)
            deadline = time.monotonic() + 10
            while True:
                try:
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        self.handle.close()
                        raise TimeoutError("Session ingestion is busy")
                    time.sleep(0.1)
        else:
            import fcntl
            fcntl.flock(self.handle, fcntl.LOCK_EX)
        return self

    def __exit__(self, *unused):
        if os.name == "nt":
            import msvcrt
            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        self.handle.close()


def messages(text):
    matches = list(ROLE.finditer(text))
    return [(match.group(1), text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)])
            for i, match in enumerate(matches)]


def user_topics(text):
    """Only user requests inform titles; quoted instructions remain inert data."""
    result = []
    for role, body in messages(text):
        if role != "user":
            continue
        body = re.sub(r"<([A-Za-z_][\w:-]*)\b[^>]*>.*?</\1>", "", body, flags=re.S)
        if "## My request:" in body:
            body = body.split("## My request:", 1)[1]
        if body.lstrip().startswith(("# AGENTS.md", "[CONTEXT COMPACTION", "Another language model")):
            continue
        body = re.sub(r"```.*?```", "", body, flags=re.S)
        body = re.sub(r"\[[^\]]*]\([^)]*\)", "", body)
        body = re.sub(r"\s+", " ", body).strip()
        if len(body) > 5 and not body.startswith("[System:"):
            result.append(body[:900])
    return result


def clean_title(value):
    value = re.sub(r"<[^>]*>", "", str(value))
    value = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", "", value, flags=re.I)
    value = re.sub(r"^[#\s\"'“”]+|[\s\"'“”]+$", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:56].rstrip("，。；：、 ")


def original_title(value):
    """Use the supplied title as the document name, without generated suffixes."""
    value = str(value).strip()
    if not value or len(value.encode("utf-8")) > 1200 or any(ord(c) < 32 for c in value):
        raise ValueError("Missing or invalid original title")
    if "/" in value or "\\" in value:
        raise ValueError("The original title contains a path separator")
    return value


def fallback_title(text):
    topics = user_topics(text)
    topic = " ".join(topics)
    folded = topic.lower()
    rules = [
        (("hindsight", "合并"), "Hindsight 文档合并、费用核算与会话归档"),
        (("千帆",), "千帆报表代码审查与接口解耦"),
        (("hermes", "迁移", "codex"), "Hermes 会话迁移与 Codex 接入"),
        (("思考", "强度"), "Codex 模型思考强度配置排查"),
        (("win10", "win11"), "Codex 跨设备配置差异与技能同步"),
        (("cpa", "密钥"), "CPA 密钥与多客户端配置同步"),
        (("hindsight",), "Hindsight 多客户端记忆接入与自动读写"),
    ]
    for words, title in rules:
        if all(word in folded for word in words):
            return title
    for item in topics:
        if re.search(r"[\u3400-\u9fff]", item):
            item = re.sub(r"^(?:请|能否|能不能|可以|帮我|麻烦|现在|你)", "", item)
            return clean_title(item) or "会话记录与处理结论"
    return "会话记录与处理结论"


def local_title(sid, text, payload=None):
    payload = payload or {}
    value = payload.get("session_title") or payload.get("conversation_title")
    if value and re.search(r"[\u3400-\u9fff]", str(value)):
        return original_title(value)
    for database in (Path.home() / ".codex").glob("state_*.sqlite"):
        try:
            connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True, timeout=0.1)
            try:
                row = connection.execute("SELECT name,title FROM threads WHERE id=?", (sid,)).fetchone()
            finally:
                connection.close()
            if row:
                for value in row:
                    if value and re.search(r"[\u3400-\u9fff]", value):
                        return original_title(value)
        except sqlite3.Error:
            continue
    raise ValueError("Original session title unavailable; provide session_title")


def normalize_path(value, cwd=None):
    value = unquote(str(value)).strip().strip("<>")
    if value.startswith("file://"):
        value = value[7:]
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", value):
        value = "/mnt/" + value[0].lower() + value[2:].replace("\\", "/")
    path = Path(value).expanduser()
    if not path.is_absolute():
        if cwd is None:
            return None
        path = Path(cwd) / path
    try:
        return path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None


def session_payload(payload):
    """Recover start time and workspace without interpreting tool output."""
    payload = dict(payload)
    location = payload.get("transcript_path") or payload.get("session_file")
    if location:
        path = normalize_path(location, os.getcwd())
        if path is not None:
            try:
                with path.open(encoding="utf-8", errors="replace") as handle:
                    first = json.loads(handle.readline())
                data = first.get("payload", first)
                if first.get("type") == "session_meta":
                    if data.get("cwd"):
                        payload.setdefault("cwd", data["cwd"])
                    timestamp = data.get("timestamp") or first.get("timestamp")
                    if timestamp:
                        payload.setdefault("session_started_at", timestamp)
                elif first.get("timestamp"):
                    payload.setdefault("session_started_at", first["timestamp"])
            except (OSError, ValueError, AttributeError):
                pass
    return payload


def artifact_candidates(text, payload=None):
    payload = payload or {}
    found = []
    for role, body in messages(text):
        if role != "assistant":
            continue
        found.extend(re.findall(r"\[[^\]\n]*]\((<[^>]+>|[^)\n]+)\)", body))
        found.extend(re.findall(r"`((?:/|[A-Za-z]:[\\/])[^`\n]+)`", body))
    for entry in payload.get("artifacts", []) or []:
        found.append(entry.get("path") if isinstance(entry, dict) else entry)
    return list(dict.fromkeys(
        re.sub(r":\d+(?:-\d+)?$", "", str(value).strip())
        for value in found if value and not str(value).startswith(("http:", "https:", "app:", "codex:"))
    ))


def allowed_artifact(path, roots, started_at=None):
    if path.suffix.lower() not in DOCUMENT_SUFFIXES or PRIVATE_NAME.search(path.name):
        return False
    if PRIVATE_COMPONENTS.intersection(path.parts) or any(part.startswith(".env") for part in path.parts):
        return False
    if not any(path.is_relative_to(root) for root in roots):
        return False
    limit = MAX_CONVERTED_BYTES if path.suffix.lower() in CONVERTED_SUFFIXES else MAX_BYTES
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        return False
    if started_at is not None and path.stat().st_mtime < started_at - 2:
        return False
    return True


def installation_id(state_root):
    path = Path(state_root) / "source-identity.json"
    with SessionLock(path.with_suffix(".lock")):
        state = load_state(path)
        if not state.get("source_id"):
            import uuid
            state = {"source_id": str(uuid.uuid4())}
            save_state(path, state)
    return state["source_id"]


def collect_artifacts(text, payload, source_id, cwd=None):
    """Return (ready, blocked): explicitly linked documents that passed the credential preflight.

    ready items are dicts with key, path, data and sha256. Nothing here parses document content.
    """
    payload = session_payload(payload)
    cwd = cwd or payload.get("cwd") or payload.get("workdir") or os.getcwd()
    roots = [Path(cwd).resolve()]
    for root in payload.get("workspace_roots", []) or []:
        roots.append(Path(root).expanduser().resolve())
    roots.extend(Path(root).expanduser().resolve()
                 for root in os.environ.get("HINDSIGHT_ARTIFACT_ROOTS", "").split(os.pathsep) if root)
    started_at = None
    if payload.get("session_started_at"):
        started_at = datetime.fromisoformat(payload["session_started_at"].replace("Z", "+00:00")).timestamp()
    explicit = set(str(item.get("path") if isinstance(item, dict) else item)
                   for item in payload.get("artifacts", []) or [])
    input_paths = set()
    for role, body in messages(text):
        if role == "user":
            for value in re.findall(r"(?:[A-Za-z]:[\\/]|/)[^\n<>\"`]*?\.(?:pdf|docx|pptx|xlsx|md|txt|csv|json)(?=[\s)\]：:]|$)", body):
                path = normalize_path(value, cwd)
                if path is not None:
                    input_paths.add(path)
    ready, blocked = [], []
    for candidate in artifact_candidates(text, payload):
        path = normalize_path(candidate, cwd)
        if (path is None or path in input_paths
                or (started_at is None and candidate not in explicit)
                or not allowed_artifact(path, roots, started_at)):
            continue
        try:
            data = inspect_upload(path.name, path.read_bytes())
        except (OSError, ValueError, UnicodeDecodeError, zipfile.BadZipFile, ET.ParseError) as error:
            blocked.append({"path": str(path), "reason": str(error) or type(error).__name__})
            continue
        ready.append({"key": artifact_identity(source_id, str(path)), "path": path, "data": data,
                      "sha256": hashlib.sha256(data).hexdigest()})
    return ready, blocked
