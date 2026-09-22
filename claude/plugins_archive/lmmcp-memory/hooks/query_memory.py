#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook — 查询 lmmcp 记忆注入 systemMessage。

stdin: {"hook_event_name": "UserPromptSubmit", "user_prompt": "...", "session_id": "...", ...}
stdout: {"systemMessage": "..."} 或 {}
"""
from __future__ import annotations
import json
import sys
import urllib.request
import urllib.error

LMMCP_URL = "http://127.0.0.1:8318/mcp"
TIMEOUT = 6
CONTEXT_BUDGET = 1200
FTS_LIMIT = 4
MIN_LEN = 4


def _mcp_session() -> str:
    req = urllib.request.Request(
        LMMCP_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "claude-lmmcp-hook", "version": "1.0"}
            }
        }).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.headers.get("Mcp-Session-Id", "")


def _mcp_call(sid: str, tool: str, args: dict) -> dict:
    h = {"Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid:
        h["Mcp-Session-Id"] = sid
    req = urllib.request.Request(
        LMMCP_URL,
        data=json.dumps({"jsonrpc": "2.0", "id": 1,
                         "method": "tools/call",
                         "params": {"name": tool, "arguments": args}}).encode(),
        headers=h, method="POST"
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        for line in resp.read().decode().splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return {}


def _text(r: dict) -> str:
    for item in r.get("result", {}).get("content", []):
        if item.get("type") == "text":
            return item["text"]
    return ""


def query(prompt: str) -> str:
    sid = _mcp_session()

    ctx_raw = _text(_mcp_call(sid, "memory_context",
                               {"task": prompt, "token_budget": CONTEXT_BUDGET}))
    ctx_str = ""
    if ctx_raw and ctx_raw.strip():
        try:
            d = json.loads(ctx_raw)
            ctx_str = d.get("context", "") if isinstance(d, dict) else ctx_raw
        except Exception:
            ctx_str = ctx_raw

    fts_raw = _text(_mcp_call(sid, "memory_search",
                               {"query": prompt, "limit": FTS_LIMIT})).strip()
    fts_items = []
    for line in fts_raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d2 = json.loads(line)
            title = d2.get("title", "")
            body = d2.get("content", "")[:180]
            if title:
                fts_items.append(f"- {title}: {body}")
        except Exception:
            pass

    parts = []
    if ctx_str and len(ctx_str) > 30:
        parts.append(ctx_str.strip())
    if fts_items:
        parts.append("[FTS相关记忆]\n" + "\n".join(fts_items))
    return "\n\n".join(parts)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("{}", flush=True)
        return

    prompt = data.get("user_prompt", "").strip()
    if len(prompt) < MIN_LEN:
        print("{}", flush=True)
        return

    try:
        ctx = query(prompt)
    except (urllib.error.URLError, Exception):
        print("{}", flush=True)
        return

    if not ctx:
        print("{}", flush=True)
        return

    msg = f"[lmmcp 相关记忆 — 仅供参考，请根据实际情况判断]\n{ctx}"
    print(json.dumps({"systemMessage": msg}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
