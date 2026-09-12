"""mcore-memory Hermes plugin.

pre_llm_call:
  - 用 user_message 查询 mcore (memory_context + memory_search FTS)
  - 返回 {"context": "..."} 注入当前 turn 的用户消息

post_llm_call:
  - 异步把 user_message + assistant_response ingest 到 mcore
  - 直接调用 MCP memory_ingest 工具（streamable-http），无外部二进制依赖

on_session_end:
  - 会话结束兜底：异步调用 mcore-ingest.py 读取 state.db 该会话完整
    transcript 写回，捕获 post_llm_call 未覆盖的轮次（中断/压缩等）。

设计说明：所有能力走插件系统（serve 与 CLI 启动都会 discover_plugins），
不依赖 config 里的 shell hooks —— hermes serve 路径不注册 shell hooks，
插件是 serve 下唯一可靠的 hook 通道。
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

MCORE_URL = "http://127.0.0.1:8318/mcp"
TIMEOUT = 5
CONTEXT_BUDGET = 1500
FTS_LIMIT = 5
AGENT_ID = "hermes"

# 会话结束兜底写回：复用 agent-hooks/mcore-ingest.py（读 state.db transcript）
MCORE_INGEST_SCRIPT = Path.home() / ".hermes" / "agent-hooks" / "mcore-ingest.py"
STATE_DB = Path(os.environ.get("HERMES_STATE_DB", str(Path.home() / ".hermes" / "state.db")))

# 最短 user_message 长度，太短的问候语不查询
MIN_QUERY_LEN = 4


def _session_project_path(session_id: str) -> str:
    """Current session's working dir / git repo root, read from Hermes state.db.

    The MCP-side subject resolution (subject_context.projects / auto-discover)
    turns this into a canonical project name; the LLM still decides the
    authoritative per-fact ``subject`` (对话可跨项目引用).
    """
    if not session_id or not STATE_DB.exists():
        return ""
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT git_repo_root, cwd FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT git_repo_root, cwd FROM sessions "
                    "WHERE ended_at IS NULL ORDER BY last_activity_at DESC LIMIT 1"
                ).fetchone()
            if row:
                return str(row["git_repo_root"] or "").strip() or str(row["cwd"] or "").strip()
        finally:
            conn.close()
    except Exception:
        return ""
    return ""


# ---------------------------------------------------------------------------
# MCP helpers
# ---------------------------------------------------------------------------

def _mcp_session() -> str:
    req = urllib.request.Request(
        MCORE_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "hermes-mcore-plugin", "version": "1.0"}
            }
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.headers.get("Mcp-Session-Id", "")


def _mcp_call(session_id: str, tool: str, args: dict, timeout: float = TIMEOUT) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(
        MCORE_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args}
        }).encode(),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
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


# ---------------------------------------------------------------------------
# Memory query
# ---------------------------------------------------------------------------

def _query_memory(query: str, project_path: str = "") -> str:
    """查询 mcore，返回格式化上下文字符串。失败时返回空字符串。"""
    try:
        sid = _mcp_session()

        # memory_context: 综合 FTS + profile + decision
        ctx_args: dict[str, Any] = {
            "task": query,
            "agent": AGENT_ID,
            "token_budget": CONTEXT_BUDGET,
        }
        if project_path:
            ctx_args["project_path"] = project_path
        ctx_result = _mcp_call(sid, "memory_context", ctx_args)
        ctx_text = _extract_text(ctx_result)
        if isinstance(ctx_text, str) and ctx_text.strip():
            # ctx_text 可能是 JSON {"context": "...", "records": [...]}
            try:
                d = json.loads(ctx_text)
                ctx_str = d.get("context", "") if isinstance(d, dict) else ctx_text
            except Exception:
                ctx_str = ctx_text
        else:
            ctx_str = ""

        # memory_search FTS 补充
        fts_result = _mcp_call(sid, "memory_search", {
            "query": query,
            "limit": FTS_LIMIT
        })
        fts_raw = _extract_text(fts_result).strip()
        fts_items = []
        for line in fts_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d2 = json.loads(line)
                title = d2.get("title", "")
                body = d2.get("content", "")[:200]
                tags = d2.get("tags", [])
                tag_str = f" [{', '.join(tags[:3])}]" if tags else ""
                if title:
                    fts_items.append(f"- {title}{tag_str}: {body}")
            except Exception:
                pass

        parts: list[str] = []
        if ctx_str and len(ctx_str) > 30:
            parts.append(ctx_str.strip())
        if fts_items:
            parts.append("[FTS相关记忆]\n" + "\n".join(fts_items[:FTS_LIMIT]))

        return "\n\n".join(parts)

    except urllib.error.URLError:
        logger.debug("mcore-memory: mcore 服务不可用，跳过记忆查询")
        return ""
    except Exception as exc:
        logger.debug("mcore-memory: 查询失败 %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Async ingest
# ---------------------------------------------------------------------------

def _ingest_async(session_id: str, user_message: str, assistant_response: str) -> None:
    """后台线程: 把当前问答 ingest 到 mcore。"""
    messages = [
        {"role": "user", "content": user_message[:1000]},
        {"role": "assistant", "content": assistant_response[:1000]},
    ]
    try:
        sid = _mcp_session()
        ingest_args: dict[str, Any] = {
            "messages": messages,
            "agent_id": AGENT_ID,
            "timeout_s": 120,
        }
        project_path = _session_project_path(session_id)
        if project_path:
            ingest_args["project_path"] = project_path
        result = _mcp_call(sid, "memory_ingest", ingest_args, timeout=60)
        logger.info("mcore-memory: ingest result %s", result)
    except Exception as exc:
        logger.warning("mcore-memory: ingest 失败 %s", exc)


# ---------------------------------------------------------------------------
# Hook handlers
# ---------------------------------------------------------------------------

def _on_pre_llm_call(**kwargs: Any):
    """查询 mcore，返回记忆上下文注入 user message。"""
    user_message: str = kwargs.get("user_message", "") or ""
    if len(user_message.strip()) < MIN_QUERY_LEN:
        return None

    session_id: str = kwargs.get("session_id", "") or ""
    project_path = _session_project_path(session_id)
    memory_ctx = _query_memory(user_message, project_path)
    if not memory_ctx:
        return None

    return {"context": f"\n---\n{memory_ctx}\n---\n"}


def _on_post_llm_call(**kwargs: Any):
    """异步 ingest 问答对到 mcore。"""
    session_id: str = kwargs.get("session_id", "") or ""
    user_message: str = kwargs.get("user_message", "") or ""
    assistant_response: str = kwargs.get("assistant_response", "") or ""

    if not user_message.strip() or not assistant_response.strip():
        return

    t = threading.Thread(
        target=_ingest_async,
        args=(session_id, user_message, assistant_response),
        daemon=True,
        name="mcore-ingest"
    )
    t.start()


def _on_session_end(**kwargs: Any):
    """会话结束兜底：把整个会话 transcript 写回 mcore。

    post_llm_call 覆盖每轮问答；此 hook 捕获中断/压缩等未写回的轮次。
    """
    script_path = MCORE_INGEST_SCRIPT
    if not script_path.exists():
        fallback_script = Path("/workspace/memorycore/scripts/hooks/mcore-ingest.py")
        if fallback_script.exists():
            script_path = fallback_script
        else:
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
            logger.debug("mcore-memory: session-end ingest 失败 %s", exc)

    t = threading.Thread(target=_run, daemon=True, name="mcore-session-end")
    t.start()


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
    logger.info("mcore-memory plugin registered (pre_llm_call + post_llm_call + on_session_end)")
