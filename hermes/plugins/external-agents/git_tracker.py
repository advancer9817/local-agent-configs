"""Git status and diff tracking utility for external-agents plugin."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def is_git_repo(directory: Path | str) -> bool:
    """Check if the given directory is inside a Git repository."""
    dir_path = Path(directory).resolve()
    if not dir_path.is_dir():
        return False
    try:
        res = subprocess.run(
            ["git", "-C", str(dir_path), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False


def get_git_state(directory: Path | str) -> dict[str, Any]:
    """Capture baseline Git state before running an agent task."""
    dir_path = Path(directory).resolve()
    if not is_git_repo(dir_path):
        return {"is_git": False, "head": None, "porcelain": []}

    head = None
    try:
        res_head = subprocess.run(
            ["git", "-C", str(dir_path), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res_head.returncode == 0:
            head = res_head.stdout.strip()
    except Exception:
        pass

    porcelain = []
    try:
        res_status = subprocess.run(
            ["git", "-C", str(dir_path), "status", "--porcelain=v1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res_status.returncode == 0:
            porcelain = [line.strip() for line in res_status.stdout.splitlines() if line.strip()]
    except Exception:
        pass

    return {"is_git": True, "head": head, "porcelain": porcelain}


def get_git_diff(directory: Path | str, baseline_state: dict[str, Any]) -> dict[str, Any]:
    """Compute files changed and git diff against baseline state."""
    dir_path = Path(directory).resolve()
    if not baseline_state.get("is_git") or not is_git_repo(dir_path):
        return {
            "is_git": False,
            "files_changed": [],
            "diff_stat": "",
            "diff_summary": "",
            "has_changes": False,
        }

    # Current status
    current_porcelain = []
    try:
        res_status = subprocess.run(
            ["git", "-C", str(dir_path), "status", "--porcelain=v1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res_status.returncode == 0:
            current_porcelain = [line.strip() for line in res_status.stdout.splitlines() if line.strip()]
    except Exception:
        pass

    # Diff stat
    diff_stat = ""
    try:
        res_stat = subprocess.run(
            ["git", "-C", str(dir_path), "diff", "--stat"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        if res_stat.returncode == 0:
            diff_stat = res_stat.stdout.strip()
    except Exception:
        pass

    # Diff patch snippet (max 3000 chars)
    diff_summary = ""
    try:
        res_diff = subprocess.run(
            ["git", "-C", str(dir_path), "diff"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        if res_diff.returncode == 0:
            diff_text = res_diff.stdout.strip()
            if len(diff_text) > 3000:
                diff_summary = diff_text[:3000] + "\n... [diff truncated]"
            else:
                diff_summary = diff_text
    except Exception:
        pass

    # Extract changed files compared to baseline
    baseline_set = set(baseline_state.get("porcelain", []))
    new_status = [line for line in current_porcelain if line not in baseline_set]

    files_changed: list[str] = []
    for item in new_status:
        # e.g. "M path/file.py", "?? new_file.txt", "A added.py"
        parts = item.split(None, 1)
        if len(parts) == 2:
            files_changed.append(parts[1])
        else:
            files_changed.append(item)

    # If diff_stat is present but files_changed was empty (e.g. preexisting unstaged edits were modified further)
    if not files_changed and diff_stat:
        for line in diff_stat.splitlines()[:-1]:  # exclude the summary line
            parts = line.split("|", 1)
            if parts:
                f = parts[0].strip()
                if f and f not in files_changed:
                    files_changed.append(f)

    return {
        "is_git": True,
        "files_changed": files_changed,
        "diff_stat": diff_stat,
        "diff_summary": diff_summary,
        "has_changes": bool(files_changed or diff_stat),
    }
