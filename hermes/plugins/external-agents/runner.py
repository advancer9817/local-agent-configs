"""Execution runner for Claude Code and Codex CLIs with PTY-driven supervision."""

from __future__ import annotations

import json
import os
import pty
import re
import select
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

try:
    from . import git_tracker
except (ImportError, ValueError):
    import git_tracker

_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),
    re.compile(r"xox[baprs]-[a-zA-Z0-9_\-]{10,}"),
    re.compile(r"(api[_-]?key|secret|token)[\s:=]+([\"']?[a-zA-Z0-9_\-]{16,}[\"']?)", re.IGNORECASE),
]

_ANSI_ESCAPE_PATTERN = re.compile(r"(?:[@-Z\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """Remove ANSI terminal escape codes from text."""
    return _ANSI_ESCAPE_PATTERN.sub("", text)


def redact_secrets(text: str) -> str:
    """Redact keys and tokens from terminal/agent output."""
    if not text:
        return ""
    sanitized = text
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


def find_executable(name: str) -> str | None:
    """Locate executable in PATH or standard system directories."""
    path = shutil.which(name)
    if path and os.path.isfile(path) and os.access(path, os.X_OK):
        return path
    for fallback in [f"/usr/local/bin/{name}", f"/usr/bin/{name}"]:
        if os.path.isfile(fallback) and os.access(fallback, os.X_OK):
            return fallback
    return None


def _get_claude_env() -> dict[str, str]:
    """Resolve environment variables for Claude Code aligning with user config."""
    env = os.environ.copy()

    settings_file = Path.home() / ".claude" / "settings.json"
    if settings_file.is_file():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            file_env = data.get("env", {})
            for k, v in file_env.items():
                if isinstance(v, str) and k not in env:
                    env[k] = v
        except Exception:
            pass

    if "ANTHROPIC_BASE_URL" not in env:
        env["ANTHROPIC_BASE_URL"] = "http://35.236.134.50:8317"
    if "ANTHROPIC_MODEL" not in env:
        env["ANTHROPIC_MODEL"] = "gemini-3.8-flash[1M]"

    env["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "0"
    env["CLAUDE_CODE_ENABLE_SUBAGENTS"] = "0"
    env["CLAUDE_CODE_DISABLE_BACKGROUND_AGENTS"] = "1"
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def execute_claude(
    prompt: str,
    workdir: str = ".",
    allowed_tools: str | None = None,
    danger_skip_permissions: bool = True,
    timeout: int = 300,
    status_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Execute a task via Claude Code CLI supervised inside a native PTY."""
    claude_bin = find_executable("claude")
    if not claude_bin:
        return {
            "success": False,
            "agent": "claude-code",
            "exit_code": -1,
            "error": "claude CLI executable not found in PATH or /usr/local/bin",
            "output": "",
        }

    work_path = Path(workdir).resolve()
    if not work_path.exists() or not work_path.is_dir():
        return {
            "success": False,
            "agent": "claude-code",
            "exit_code": -1,
            "error": f"Specified workdir does not exist: {workdir}",
            "output": "",
        }

    baseline = git_tracker.get_git_state(work_path)

    cmd = [claude_bin, "-p", prompt]
    if danger_skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    if allowed_tools:
        cmd.extend(["--allowedTools", allowed_tools])

    claude_env = _get_claude_env()

    master, slave = pty.openpty()
    start_time = time.monotonic()
    timed_out = False
    raw_output_chunks: list[bytes] = []
    milestones: list[dict[str, Any]] = [{"stage": "started", "time_offset_s": 0.0}]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(work_path),
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
            env=claude_env,
        )
        os.close(slave)

        current_stage = "initializing"
        while True:
            elapsed = time.monotonic() - start_time
            if elapsed > timeout:
                timed_out = True
                try:
                    proc.kill()
                except OSError:
                    pass
                break

            r, _, _ = select.select([master], [], [], 0.5)
            if r:
                try:
                    chunk = os.read(master, 4096)
                    if not chunk:
                        break
                    raw_output_chunks.append(chunk)

                    text_chunk = strip_ansi(chunk.decode("utf-8", errors="ignore"))
                    new_stage = None
                    if "Thinking..." in text_chunk or "Thought:" in text_chunk:
                        new_stage = "thinking"
                    elif "Running" in text_chunk or "Bash(" in text_chunk or "Edit(" in text_chunk:
                        new_stage = "executing_tools"
                    elif "Cost:" in text_chunk or "Done." in text_chunk:
                        new_stage = "completing"

                    if new_stage and new_stage != current_stage:
                        current_stage = new_stage
                        milestone_entry = {
                            "stage": current_stage,
                            "time_offset_s": round(elapsed, 2),
                        }
                        milestones.append(milestone_entry)
                        if status_callback:
                            status_callback(milestone_entry)

                except OSError:
                    break

            if proc.poll() is not None:
                while True:
                    r_rest, _, _ = select.select([master], [], [], 0.1)
                    if not r_rest:
                        break
                    try:
                        chunk = os.read(master, 4096)
                        if not chunk:
                            break
                        raw_output_chunks.append(chunk)
                    except OSError:
                        break
                break

        returncode = proc.poll() if proc.poll() is not None else (-9 if timed_out else 0)

    except Exception as exc:
        try:
            os.close(master)
        except OSError:
            pass
        return {
            "success": False,
            "agent": "claude-code",
            "exit_code": -1,
            "duration_s": round(time.monotonic() - start_time, 2),
            "error": f"Failed to spawn claude process: {exc}",
            "output": "",
        }

    try:
        os.close(master)
    except OSError:
        pass

    duration = round(time.monotonic() - start_time, 2)
    milestones.append({"stage": "finished", "time_offset_s": duration})

    full_raw = b"".join(raw_output_chunks).decode("utf-8", errors="ignore")
    clean_text = strip_ansi(full_raw).strip()
    output = redact_secrets(clean_text)

    git_diff_res = git_tracker.get_git_diff(work_path, baseline)

    error_msg = None
    if timed_out:
        error_msg = f"Claude Code execution timed out after {timeout} seconds"
    elif returncode != 0:
        error_msg = f"Claude Code exited with status {returncode}"

    return {
        "success": returncode == 0 and not timed_out,
        "agent": "claude-code",
        "exit_code": returncode,
        "duration_s": duration,
        "workdir": str(work_path),
        "milestones": milestones,
        "files_changed": git_diff_res.get("files_changed", []),
        "diff_stat": git_diff_res.get("diff_stat", ""),
        "diff_summary": git_diff_res.get("diff_summary", ""),
        "output": output,
        "error": error_msg,
    }


def execute_codex(
    prompt: str,
    workdir: str = ".",
    sandbox: str = "workspace-write",
    timeout: int = 300,
) -> dict[str, Any]:
    """Execute a task via OpenAI Codex CLI in non-interactive exec mode."""
    codex_bin = find_executable("codex")
    if not codex_bin:
        return {
            "success": False,
            "agent": "codex",
            "exit_code": -1,
            "error": "codex CLI executable not found in PATH or /usr/local/bin",
            "output": "",
        }

    work_path = Path(workdir).resolve()
    if not work_path.exists() or not work_path.is_dir():
        return {
            "success": False,
            "agent": "codex",
            "exit_code": -1,
            "error": f"Specified workdir does not exist: {workdir}",
            "output": "",
        }

    if not git_tracker.is_git_repo(work_path):
        return {
            "success": False,
            "agent": "codex",
            "exit_code": -1,
            "error": (
                f"Directory '{work_path}' is not a Git repository. "
                "Codex requires a git repository to operate. Please run 'git init' first."
            ),
            "output": "",
        }

    baseline = git_tracker.get_git_state(work_path)

    cmd = [codex_bin, "exec", prompt, "--sandbox", sandbox]

    start_time = time.monotonic()
    timed_out = False
    stdout_data = ""
    stderr_data = ""
    returncode = 0

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(work_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )
        try:
            stdout_data, stderr_data = proc.communicate(timeout=timeout)
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            stdout_data, stderr_data = proc.communicate()
            returncode = -9
    except Exception as exc:
        return {
            "success": False,
            "agent": "codex",
            "exit_code": -1,
            "duration_s": round(time.monotonic() - start_time, 2),
            "error": f"Failed to spawn codex process: {exc}",
            "output": "",
        }

    duration = round(time.monotonic() - start_time, 2)
    git_diff_res = git_tracker.get_git_diff(work_path, baseline)

    output = redact_secrets(stdout_data.strip())
    stderr_clean = redact_secrets(stderr_data.strip())
    if stderr_clean and returncode != 0:
        output = f"{output}\n[STDERR]\n{stderr_clean}".strip()

    error_msg = None
    if timed_out:
        error_msg = f"Codex execution timed out after {timeout} seconds"
    elif returncode != 0:
        error_msg = f"Codex exited with status {returncode}"

    return {
        "success": returncode == 0 and not timed_out,
        "agent": "codex",
        "exit_code": returncode,
        "duration_s": duration,
        "workdir": str(work_path),
        "files_changed": git_diff_res.get("files_changed", []),
        "diff_stat": git_diff_res.get("diff_stat", ""),
        "diff_summary": git_diff_res.get("diff_summary", ""),
        "output": output,
        "error": error_msg,
    }
