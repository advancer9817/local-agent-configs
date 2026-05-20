"""lmmcp-memory Hermes plugin.

pre_llm_call:
  - 用 user_message 查询 lmmcp (memory_context + memory_search FTS)
  - 返回 {"context": "..."} 注入当前 turn 的用户消息

post_llm_call:
  - 异步把 user_message + assistant_response ingest 到 lmmcp
  - 使用 lmmcp-ingest 二进制（已有，支持 streamable-http）
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LMMCP_URL = "http://127.0.0.1:8318/mcp"
TIMEOUT = 5
CONTEXT_BUDGET = 1500
FTS_LIMIT = 5
INGEST_BIN = Path.home() / ".local/bin/lmmcp-ingest"

# 最短 user_message 长度，太短的问候语不查询
MIN_QUERY_LEN = 4


# ---------------------------------------------------------------------------
# MCP helpers
# ---------------------------------------------------------------------------

def _mcp_session() -> str:
    req = urllib.request.Request(
        LMMCP_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "hermes-lmmcp-plugin", "version": "1.0"}
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


def _mcp_call(session_id: str, tool: str, args: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(
        LMMCP_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args}
        }).encode(),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read().decode()
        for line in body.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
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

def _query_memory(query: str) -> str:
    """查询 lmmcp，返回格式化上下文字符串。失败时返回空字符串。"""
    try:
        sid = _mcp_session()

        # memory_context: 综合 FTS + profile + decision
        ctx_result = _mcp_call(sid, "memory_context", {
            "task": query,
            "token_budget": CONTEXT_BUDGET
        })
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
        logger.debug("lmmcp-memory: lmmcp 服务不可用，跳过记忆查询")
        return ""
    except Exception as exc:
        logger.debug("lmmcp-memory: 查询失败 %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Async ingest
# ---------------------------------------------------------------------------

def _ingest_async(session_id: str, user_message: str, assistant_response: str) -> None:
    """后台线程: 把当前问答 ingest 到 lmmcp。"""
    if not INGEST_BIN.exists():
        return
    messages = [
        {"role": "user", "content": user_message[:1000]},
        {"role": "assistant", "content": assistant_response[:1000]},
    ]
    payload = json.dumps({
        "session_id": session_id,
        "messages": messages
    })
    try:
        subprocess.run(
            [str(INGEST_BIN), "--min-turns", "1"],
            input=payload.encode(),
            capture_output=True,
            timeout=15
        )
    except Exception as exc:
        logger.debug("lmmcp-memory: ingest 失败 %s", exc)


# ---------------------------------------------------------------------------
# Hook handlers
# ---------------------------------------------------------------------------

def _on_pre_llm_call(**kwargs: Any):
    """查询 lmmcp，返回记忆上下文注入 user message。"""
    user_message: str = kwargs.get("user_message", "") or ""
    if len(user_message.strip()) < MIN_QUERY_LEN:
        return None

    memory_ctx = _query_memory(user_message)
    if not memory_ctx:
        return None

    return {"context": f"\n---\n{memory_ctx}\n---\n"}


def _on_post_llm_call(**kwargs: Any):
    """异步 ingest 问答对到 lmmcp。"""
    session_id: str = kwargs.get("session_id", "") or ""
    user_message: str = kwargs.get("user_message", "") or ""
    assistant_response: str = kwargs.get("assistant_response", "") or ""

    if not user_message.strip() or not assistant_response.strip():
        return

    t = threading.Thread(
        target=_ingest_async,
        args=(session_id, user_message, assistant_response),
        daemon=True,
        name="lmmcp-ingest"
    )
    t.start()


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    logger.info("lmmcp-memory plugin registered (pre_llm_call + post_llm_call)")
