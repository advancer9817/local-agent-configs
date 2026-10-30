"""Hindsight for Hermes: the same hindsight-hook.py that Codex and Claude Code run.

pre_llm_call   recall for the user's message; returned as {"context": ...} (API-time only, not persisted).
post_llm_call  after the turn is persisted, upload the complete session read from state.db.
on_session_end catches interrupted or failed turns; unchanged sessions are skipped by the hook.

Shell hooks are not registered under `hermes serve`, so a plugin is the reliable channel.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

HOOK = Path(os.environ.get("HINDSIGHT_HOOK_SCRIPT", str(Path.home() / ".local/lib/hindsight/hindsight-hook.py")))
RECALL_TIMEOUT = 20
RETAIN_TIMEOUT = 180
MIN_QUERY_LEN = 4
_running: set[str] = set()
_pending: set[str] = set()
_lock = threading.Lock()


def _python() -> str:
    return os.environ.get("HINDSIGHT_PYTHON") or sys.executable or "python3"


def _state_db() -> str:
    try:
        from hermes_constants import get_hermes_home
        return str(Path(get_hermes_home()) / "state.db")
    except Exception:
        return str(Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "state.db")


def _run(action: str, payload: dict, timeout: int) -> str:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    done = subprocess.run([_python(), str(HOOK), action, "--agent", "hermes"], input=json.dumps(payload).encode(),
                          capture_output=True, timeout=timeout, creationflags=flags)
    if done.stderr:
        logger.warning("hindsight-memory %s: %s", action, done.stderr.decode(errors="replace").strip()[-500:])
    return done.stdout.decode(errors="replace").strip()


def _on_pre_llm_call(**kwargs):
    message = kwargs.get("user_message")
    if not isinstance(message, str) or len(message.strip()) < MIN_QUERY_LEN or not HOOK.exists():
        return None
    try:
        context = _run("recall", {"prompt": message, "session_id": kwargs.get("session_id") or ""}, RECALL_TIMEOUT)
    except Exception as exc:
        logger.warning("hindsight-memory recall skipped: %s", type(exc).__name__)
        return None
    return {"context": context} if context else None


def _retain_loop(session_id: str) -> None:
    # One upload per session at a time; a turn finishing mid-upload triggers one more pass.
    while True:
        with _lock:
            if session_id not in _pending:
                _running.discard(session_id)
                return
            _pending.discard(session_id)
        try:
            _run("retain", {"session_id": session_id, "hermes_state_db": _state_db()}, RETAIN_TIMEOUT)
        except Exception as exc:
            logger.warning("hindsight-memory retain failed: %s", type(exc).__name__)


def _schedule(session_id: str) -> None:
    if not session_id or not HOOK.exists():
        return
    with _lock:
        _pending.add(session_id)
        if session_id in _running:
            return
        _running.add(session_id)
    # Not a daemon: a CLI exiting right after its last turn still finishes that upload.
    threading.Thread(target=_retain_loop, args=(session_id,), daemon=False, name="hindsight-retain").start()


def _on_post_llm_call(**kwargs):
    _schedule(str(kwargs.get("session_id") or ""))


def _on_session_end(**kwargs):
    if kwargs.get("interrupted") or kwargs.get("failed") or "completed" not in kwargs:
        _schedule(str(kwargs.get("session_id") or ""))


def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
