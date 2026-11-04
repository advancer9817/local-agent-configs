#!/usr/bin/env python3
"""hindsight-ingest.py — Stop hook: store the whole conversation transcript into Hindsight.

Strategy A: concatenate the recent transcript into a single document and call
Hindsight MCP `retain` once. Hindsight's server-side pipeline performs fact
extraction and cross-source consolidation on the document.

Reuses the battle-tested transcript extractors from the mcore ingest hook
(hermes state.db / claude jsonl / codex jsonl / opencode db / gemini), but the
write path targets Hindsight's `retain` tool over the authenticated public MCP
endpoint instead of mcore's `memory_ingest`.

Always exits 0-ish; failure must never block session end.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

MARK = Path("/tmp/hindsight-session-mark")
LOG = Path(os.environ.get("HINDSIGHT_INGEST_LOG", "/tmp/hindsight-ingest.log"))


def _log(message: str) -> None:
    try:
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {message}\n")
    except Exception:
        pass


def _spawn_background(agent: str, force: bool) -> None:
    cmd = [sys.executable or "python3", str(Path(__file__).resolve()), "--agent", agent]
    if force:
        cmd.append("--force")
    env = os.environ.copy()
    env["HINDSIGHT_INGEST_BACKGROUND_CHILD"] = "1"
    try:
        payload = sys.stdin.read()
    except Exception:
        payload = ""
    if payload:
        env["HINDSIGHT_INGEST_HOOK_PAYLOAD"] = payload[:20000]
        env["MCORE_HERMES_HOOK_PAYLOAD"] = payload[:20000]
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            close_fds=True,
            start_new_session=True,
        )
        _log(f"background_spawned agent={agent} pid={proc.pid}")
    except Exception as exc:
        _log(f"background_spawn_failed agent={agent} error={type(exc).__name__}")


def _hindsight_url() -> str:
    return os.environ.get(
        "HINDSIGHT_MCP_URL",
        "http://35.236.134.50:18888/mcp/agent-memory/",
    )


def _hindsight_token() -> str:
    if os.environ.get("HINDSIGHT_TOKEN"):
        return os.environ["HINDSIGHT_TOKEN"]
    token_file = Path(os.environ.get("HINDSIGHT_TOKEN_FILE", str(Path.home() / ".hermes" / ".hindsight-token")))
    try:
        return token_file.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _claude_roots() -> list[Path]:
    roots = [Path.home() / ".claude" / "projects"]
    w_users = Path("/mnt/c/Users")
    if w_users.exists():
        for u in w_users.iterdir():
            if u.is_dir() and not u.name.lower().startswith(("public", "default", "all users")):
                p = u / ".claude" / "projects"
                if p.exists():
                    roots.append(p)
    return roots


def _detect_project(agent: str = "") -> str:
    path = os.environ.get("MCORE_PROJECT_PATH", "").strip()
    if not path and agent == "hermes":
        try:
            db = Path(os.environ.get("HERMES_STATE_DB", str(Path.home() / ".hermes" / "state.db")))
            if db.exists():
                session_id = _payload_session_id(_hook_payload())
                conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
                conn.row_factory = sqlite3.Row
                try:
                    if session_id:
                        row = conn.execute(
                            "SELECT git_repo_root, cwd FROM sessions WHERE id = ?", (session_id,)
                        ).fetchone()
                    else:
                        row = conn.execute(
                            "SELECT git_repo_root, cwd FROM sessions "
                            "WHERE ended_at IS NULL ORDER BY last_activity_at DESC LIMIT 1"
                        ).fetchone()
                    if row:
                        path = str(row["git_repo_root"] or "").strip() or str(row["cwd"] or "").strip()
                finally:
                    conn.close()
        except Exception:
            path = ""
    if not path:
        try:
            cwd = os.environ.get("MCORE_CWD") or os.getcwd()
            proc = subprocess.run(
                ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5,
            )
            if proc.returncode == 0:
                path = proc.stdout.strip()
        except Exception:
            path = ""
    return path


def _curl_post(payload: dict, session_id: str = "", timeout: float = 10.0) -> tuple[dict, str]:
    token = _hindsight_token()
    cmd = [
        "curl", "-sS", "-i", "--noproxy", "*", "--max-time", str(timeout),
        "-X", "POST", _hindsight_url(),
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json, text/event-stream",
    ]
    if token:
        cmd.extend(["-H", f"Authorization: Bearer {token}"])
    if session_id:
        cmd.extend(["-H", f"Mcp-Session-Id: {session_id}"])
    cmd.extend(["-d", json.dumps(payload, ensure_ascii=False)])

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
    if proc.returncode != 0:
        _log(f"curl_failed rc={proc.returncode} stderr={proc.stderr.strip()[:300]}")
        return {}, ""

    raw = proc.stdout.replace("\r\n", "\n")
    if "\n\n" in raw:
        header_text, body = raw.split("\n\n", 1)
    else:
        header_text, body = raw, ""
    headers: dict[str, str] = {}
    for line in header_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers, body


def _find_transcript(roots, env_key: str, pattern: str):
    explicit = os.environ.get(env_key, "")
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
    root_list = [roots] if isinstance(roots, Path) else roots
    candidates = []
    for root in root_list:
        if not root.exists():
            continue
        try:
            candidates.extend([p for p in root.glob(pattern) if p.is_file()])
        except Exception:
            pass
    if not candidates:
        return None
    if MARK.exists():
        try:
            mark_time = MARK.stat().st_mtime
            recent = [p for p in candidates if p.stat().st_mtime >= mark_time]
        except Exception:
            recent = []
        if recent:
            return max(recent, key=lambda p: p.stat().st_mtime)
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _text_from_blocks(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return " ".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and (block.get("type") in (None, "text")) and block.get("text")
    )


def _parse_json_text(value) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _hook_payload() -> dict:
    raw = os.environ.get("HINDSIGHT_INGEST_HOOK_PAYLOAD") or os.environ.get("MCORE_HERMES_HOOK_PAYLOAD")
    if not raw:
        try:
            raw = sys.stdin.read()
        except Exception:
            raw = ""
    return _parse_json_text(raw or "{}")


def _payload_session_id(payload: dict) -> str:
    candidates = [payload.get("session_id"), payload.get("sessionID"), payload.get("sessionId"), payload.get("id")]
    session = payload.get("session")
    if isinstance(session, dict):
        candidates.extend([session.get("id"), session.get("session_id"), session.get("sessionID")])
    for value in candidates:
        if value:
            return str(value)
    return ""


def _payload_transcript_path(payload: dict):
    candidates = [payload.get("transcript_path"), payload.get("transcriptPath"), payload.get("transcript")]
    session = payload.get("session")
    if isinstance(session, dict):
        candidates.extend([session.get("transcript_path"), session.get("transcriptPath")])
    for value in candidates:
        if not value:
            continue
        path = Path(str(value)).expanduser()
        if path.is_file():
            return path
    return None


def _extract_claude(path: Path):
    messages = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-5000:]:
        try:
            item = json.loads(line)
        except Exception:
            continue
        msg = item.get("message", item)
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        if role not in ("user", "assistant"):
            continue
        text = _text_from_blocks(msg.get("content", "")).strip()
        if text:
            messages.append({"role": role, "content": text[:2000]})
    return messages[-500:]


def _extract_codex(path: Path):
    messages, fallback = [], []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-5000:]:
        try:
            item = json.loads(line)
        except Exception:
            continue
        payload = item.get("payload", {})
        if not isinstance(payload, dict):
            continue
        role = text = ""
        if item.get("type") == "event_msg":
            et = payload.get("type")
            if et == "user_message":
                role, text = "user", str(payload.get("message", ""))
            elif et == "agent_message":
                role, text = "assistant", str(payload.get("message", ""))
        elif item.get("type") == "response_item" and payload.get("type") == "message":
            role = str(payload.get("role", ""))
            if role not in ("user", "assistant"):
                continue
            parts = payload.get("content", [])
            if isinstance(parts, list):
                text = " ".join(
                    str(p.get("text") or p.get("input_text") or p.get("output_text") or "")
                    for p in parts if isinstance(p, dict)
                )
        text = text.strip()
        if not (role in ("user", "assistant") and text):
            continue
        msg = {"role": role, "content": text[:2000]}
        (messages if item.get("type") == "event_msg" else fallback).append(msg)
    if not messages:
        messages = fallback
    return messages[-500:]


def _extract_hermes(session_id: str):
    db_path = Path(os.environ.get("HERMES_STATE_DB", str(Path.home() / ".hermes" / "state.db")))
    if not db_path.exists() or not session_id:
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = ? AND role IN ('user', 'assistant')
              AND content IS NOT NULL AND trim(content) != ''
            ORDER BY id DESC LIMIT 800
            """,
            (session_id,),
        ).fetchall()
    except Exception as exc:
        _log(f"hermes_state_db_error type={type(exc).__name__}")
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    messages = []
    for row in reversed(rows):
        text = str(row["content"] or "").strip()
        if text:
            messages.append({"role": str(row["role"]), "content": text[:2000]})
    return messages[-500:]


def _opencode_data_dir() -> Path:
    return Path(os.environ.get("OPENCODE_DATA_DIR", str(Path.home() / ".local" / "share" / "opencode")))


def _extract_opencode(session_id: str = ""):
    db_path = Path(os.environ.get("OPENCODE_DB", str(_opencode_data_dir() / "opencode.db")))
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        if not session_id:
            row = conn.execute("SELECT id FROM session ORDER BY time_updated DESC LIMIT 1").fetchone()
            session_id = str(row["id"]) if row else ""
        if not session_id:
            return []
        rows = conn.execute(
            """
            SELECT m.id AS message_id, m.data AS message_data, p.data AS part_data
            FROM message m LEFT JOIN part p ON p.message_id = m.id
            WHERE m.session_id = ? ORDER BY m.time_created ASC, p.time_created ASC
            """,
            (session_id,),
        ).fetchall()
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    grouped, order = {}, []
    for row in rows:
        mid = str(row["message_id"])
        message = grouped.get(mid)
        if message is None:
            info = _parse_json_text(row["message_data"])
            message = {"role": str(info.get("role", "")), "parts": []}
            grouped[mid] = message
            order.append(mid)
        pdata = _parse_json_text(row["part_data"])
        if pdata.get("type") == "text" and str(pdata.get("text", "")).strip():
            message["parts"].append(str(pdata["text"]).strip())
    messages = []
    for mid in order:
        m = grouped[mid]
        if m.get("role") not in ("user", "assistant"):
            continue
        text = " ".join(str(p) for p in m.get("parts", []) if str(p).strip()).strip()
        if text:
            messages.append({"role": m["role"], "content": text[:2000]})
    return messages[-500:]


def _messages_for_agent(agent: str):
    if agent == "hermes":
        return _extract_hermes(_payload_session_id(_hook_payload()))
    if agent == "codex":
        path = _find_transcript(Path.home() / ".codex" / "sessions", "CODEX_SESSION_FILE", "**/*.jsonl")
        return _extract_codex(path) if path else []
    if agent == "claude":
        path = _find_transcript(_claude_roots(), "CLAUDE_SESSION_FILE", "*/*.jsonl")
        return _extract_claude(path) if path else []
    if agent == "opencode":
        return _extract_opencode(_payload_session_id(_hook_payload()))
    return []


def _build_document(messages: list, agent: str, project: str) -> str:
    """Flatten the transcript into a single readable document for Hindsight retain."""
    header_bits = [f"Conversation transcript (agent: {agent}"]
    if project:
        header_bits.append(f", project: {project}")
    header_bits.append(f", ended: {datetime.now().astimezone().isoformat(timespec='seconds')})")
    lines = ["".join(header_bits), ""]
    for m in messages:
        role = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def _ingest(messages: list, agent_id: str) -> None:
    if not messages:
        _log(f"skip_empty_messages agent={agent_id}")
        return
    try:
        ingest_timeout = float(os.environ.get("HINDSIGHT_INGEST_TIMEOUT", "120"))
        _log(f"ingest_start agent={agent_id} messages={len(messages)}")
        headers, _ = _curl_post(
            {
                "jsonrpc": "2.0", "id": 0, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "hindsight-ingest-hook", "version": "1.0"},
                },
            },
            timeout=20,
        )
        session_id = headers.get("mcp-session-id", "")
        if not session_id:
            _log(f"initialize_missing_session agent={agent_id}")
            return

        project = _detect_project(agent_id)
        document = _build_document(messages, agent_id, project)
        # Byte-bounded to keep the retain payload sane (server also extracts).
        document = document.encode("utf-8")[:60000].decode("utf-8", errors="ignore")
        tags = [f"agent:{agent_id}", "source:session-transcript"]
        if project:
            tags.append(f"project:{Path(project).name}")

        _, body = _curl_post(
            {
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {
                    "name": "retain",
                    "arguments": {
                        "content": document,
                        "context": f"session-{agent_id}",
                        "tags": tags,
                    },
                },
            },
            session_id=session_id,
            timeout=ingest_timeout,
        )
        preview = " ".join(body.split())[:500]
        _log(f"ingest_done agent={agent_id} messages={len(messages)} response={preview}")

        try:
            resp = json.loads(body) if body.strip().startswith("{") else {}
            if not resp:
                for line in body.splitlines():
                    if line.startswith("data:"):
                        resp = json.loads(line[5:].strip())
                        break
            ok = "result" in resp and not resp.get("error")
            report = {
                "timestamp": datetime.now().isoformat(),
                "agent": agent_id,
                "backend": "hindsight",
                "retained": 1 if ok else 0,
                "messages": len(messages),
                "degraded": not ok,
                "read": False,
            }
            report_path = Path.home() / ".agent-memory" / "last_ingest.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as r_exc:
            _log(f"ingest_report_save_failed: {r_exc}")
    except Exception as exc:
        import traceback
        _log(f"ingest_exception agent={agent_id} tb={traceback.format_exc()[-1500:]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Store recent agent transcript into Hindsight via retain")
    parser.add_argument("--agent", default=os.environ.get("MCORE_AGENT_ID", "claude"))
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    agent = args.agent.strip().lower()
    if args.background and os.environ.get("HINDSIGHT_INGEST_BACKGROUND_CHILD") != "1":
        _spawn_background(agent, args.force)
        return
    messages = _messages_for_agent(agent)
    _ingest(messages, agent)


if __name__ == "__main__":
    main()
