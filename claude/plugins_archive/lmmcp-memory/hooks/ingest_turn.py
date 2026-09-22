#!/usr/bin/env python3
"""Claude Code Stop hook — 把最后一轮问答 ingest 到 lmmcp。

stdin: {"hook_event_name": "Stop", "session_id": "...", "transcript_path": "...", ...}
stdout: {} (不阻断)
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

INGEST_BIN = Path.home() / ".local/bin/lmmcp-ingest"
MAX_CONTENT = 1200


def _last_turn(transcript_path: str) -> tuple[str, str]:
    """从 transcript 文件提取最后一轮 user/assistant 消息。"""
    p = Path(transcript_path)
    if not p.exists():
        return "", ""
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        user_msg = ""
        asst_msg = ""
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                role = d.get("role", "")
                content = d.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                content = str(content).strip()[:MAX_CONTENT]
                if role == "assistant" and not asst_msg:
                    asst_msg = content
                elif role == "user" and not user_msg:
                    user_msg = content
                if user_msg and asst_msg:
                    break
            except Exception:
                continue
        return user_msg, asst_msg
    except Exception:
        return "", ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("{}", flush=True)
        return

    session_id = data.get("session_id", "")
    transcript_path = data.get("transcript_path", "")

    if not INGEST_BIN.exists():
        print("{}", flush=True)
        return

    user_msg, asst_msg = _last_turn(transcript_path)
    if not user_msg or not asst_msg:
        print("{}", flush=True)
        return

    payload = json.dumps({
        "session_id": session_id,
        "messages": [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": asst_msg},
        ]
    })

    try:
        subprocess.run(
            [str(INGEST_BIN), "--min-turns", "1"],
            input=payload.encode(),
            capture_output=True,
            timeout=15
        )
    except Exception:
        pass

    print("{}", flush=True)


if __name__ == "__main__":
    main()
