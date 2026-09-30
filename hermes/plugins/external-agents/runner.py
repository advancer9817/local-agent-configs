"""Execution runner for Claude Code and Codex CLIs."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from . import git_tracker
except (ImportError, ValueError):
    import git_tracker

# Common sensitive patterns to redact
_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),
    re.compile(r"xox[baprs]-[a-zA-Z0-9_\-]{10,}"),
    re.compile(r"(api[_-]?key|secret|token)[\s:=]+([\"']?[a-zA-Z0-9_\-]{16,}[\"']?)", re.IGNORECASE),
]


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


def execute_claude(
    prompt: str,
    workdir: str = ".",
    allowed_tools: str | None = None,
    danger_skip_permissions: bool = True,
    timeout: int = 300,
) -> dict[str, Any]:
    """Execute a task via Claude Code CLI in non-interactive print mode."""
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

    # Baseline git state
    baseline = git_tracker.get_git_state(work_path)

    cmd = [claude_bin, "-p", prompt]
    if danger_skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    if allowed_tools:
        cmd.extend(["--allowedTools", allowed_tools])

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
            "agent": "claude-code",
            "exit_code": -1,
            "duration_s": round(time.monotonic() - start_time, 2),
            "error": f"Failed to spawn claude process: {exc}",
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
        error_msg = f"Claude Code execution timed out after {timeout} seconds"
    elif returncode != 0:
        error_msg = f"Claude Code exited with status {returncode}"

    return {
        "success": returncode == 0 and not timed_out,
        "agent": "claude-code",
        "exit_code": returncode,
        "duration_s": duration,
        "workdir": str(work_path),
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

    # Codex strictly requires a git repository
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
