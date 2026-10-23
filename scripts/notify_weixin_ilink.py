#!/usr/bin/env python3
"""Hermes post_llm_call hook: Send task completion notification to Weixin via Tencent iLink Bot."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))) / "cache" / "scratch" / "hermes-weixin-notify.log"

# Ensure direct connection to Tencent iLink API bypassing local proxies
for _k in ("no_proxy", "NO_PROXY"):
    _cur = os.environ.get(_k, "")
    if "weixin.qq.com" not in _cur:
        os.environ[_k] = f"{_cur},ilinkai.weixin.qq.com,novac2c.cdn.weixin.qq.com" if _cur else "ilinkai.weixin.qq.com,novac2c.cdn.weixin.qq.com"


def _log(msg: str) -> None:
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {msg}\n")
    except Exception:
        pass


def _clean_query(text: str, max_len: int = 80) -> str:
    if not text:
        return "（无明文任务指令）"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    merged = " ".join(lines) if lines else text.strip()
    merged = merged.strip("`'\"")
    if len(merged) > max_len:
        return merged[:max_len] + "..."
    return merged


def _clean_summary(text: str, max_len: int = 240) -> str:
    if not text:
        return "任务已成功执行完毕。"
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        # Drop markdown horizontal rules
        if stripped in ("---", "----", "─────", "━━━━━", "___", "***", "————"):
            continue
        # Strip markdown header hashes
        while stripped.startswith("#"):
            stripped = stripped[1:].strip()
        cleaned_lines.append(stripped)

    joined = "\n".join(cleaned_lines).strip()
    if len(joined) > max_len:
        candidate = joined[:max_len]
        if "\n" in candidate:
            return candidate.rsplit("\n", 1)[0] + "..."
        return candidate + "..."
    return joined


async def main() -> None:
    try:
        # Read full payload from stdin without arbitrary byte limits
        raw_payload = sys.stdin.read()
        if not raw_payload.strip():
            return
        data = json.loads(raw_payload)
    except Exception as exc:
        _log(f"Failed to parse stdin payload: {exc}")
        return

    extra = data.get("extra") or {}
    platform = str(extra.get("platform") or data.get("platform") or "desktop")

    # If the session itself was originated from weixin gateway, avoid duplicate notification
    if platform.lower() == "weixin":
        return

    user_query = _clean_query(str(extra.get("user_message") or ""))
    assistant_resp = _clean_summary(str(extra.get("assistant_response") or ""))

    if not user_query and not assistant_resp:
        return

    # Extract model name
    raw_model = str(extra.get("model") or data.get("model") or "gemini-3.8-flash")
    model_name = raw_model.split("/")[-1] if "/" in raw_model else raw_model

    # Load account & token
    hermes_home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    accounts_dir = hermes_home / "weixin" / "accounts"

    account_files = list(accounts_dir.glob("*.json"))
    account_files = [
        f for f in account_files
        if not f.name.endswith(".context-tokens.json") and not f.name.endswith(".sync.json")
    ]
    if not account_files:
        _log("No weixin account found in accounts dir")
        return

    account_file = account_files[0]
    account_id = account_file.stem
    try:
        acct_data = json.loads(account_file.read_text(encoding="utf-8"))
    except Exception as exc:
        _log(f"Failed to read account file {account_file}: {exc}")
        return

    base_url = acct_data.get("base_url", "https://ilinkai.weixin.qq.com")
    token = acct_data.get("token")
    if not token:
        _log("Account file missing token")
        return

    # Load context tokens
    tokens_file = accounts_dir / f"{account_id}.context-tokens.json"
    if not tokens_file.exists():
        _log("Context tokens file not found")
        return

    try:
        tokens_map = json.loads(tokens_file.read_text(encoding="utf-8"))
    except Exception as exc:
        _log(f"Failed to read context tokens: {exc}")
        return

    # Determine recipient
    home_channel = os.environ.get("WEIXIN_HOME_CHANNEL")
    target_user = home_channel if (home_channel and home_channel in tokens_map) else (
        list(tokens_map.keys())[0] if tokens_map else None
    )
    if not target_user:
        _log("No valid recipient user found with context token")
        return

    context_token = tokens_map.get(target_user)
    now_time = datetime.now().strftime("%H:%M:%S")

    # Format notification message: Scheme A (Modern Tech Card)
    msg_lines = [
        "🚀 **Hermes 任务执行完毕**",
        f"> 状态：`✅ 成功完成` · `💻 Desktop` · `⚡ {model_name}`",
        "",
        "📋 **任务指令**",
        f"`{user_query}`",
        "",
        "💡 **执行摘要**",
        assistant_resp,
        "",
        "────────────────────────",
        f"⏱️ 完成时间：`{now_time}`",
        "🖥️ 完整报表与详细过程可在 Hermes Desktop 查阅",
    ]
    message_text = "\n".join(msg_lines)

    # Send message via Hermes weixin module
    try:
        sys.path.insert(0, str(hermes_home / "hermes-agent"))
        from gateway.platforms.weixin import _send_message, _new_session

        async with _new_session() as session:
            resp = await _send_message(
                session,
                base_url=base_url,
                token=token,
                to=target_user,
                text=message_text,
                context_token=context_token,
                client_id=str(uuid.uuid4()),
            )
            _log(f"Sent Scheme A notification to {target_user}, message_id: {resp.get('message_id')}")
    except Exception as exc:
        _log(f"Failed to send weixin message: {exc}")


if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(main(), timeout=8.0))
    except Exception as e:
        _log(f"Main execution error: {e}")
    sys.exit(0)
