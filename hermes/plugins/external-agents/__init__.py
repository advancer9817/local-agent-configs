"""external-agents Hermes plugin: Orchestrate Claude Code and Codex CLI."""

from __future__ import annotations

import json
import logging
from typing import Any

try:
    from . import runner, schemas
except (ImportError, ValueError):
    import runner, schemas

logger = logging.getLogger(__name__)


def handle_claude_code_exec(args: dict[str, Any], **kwargs: Any) -> str:
    """Tool handler for claude_code_exec."""
    prompt = args.get("prompt", "").strip()
    if not prompt:
        return json.dumps({"success": False, "error": "Parameter 'prompt' is required."}, ensure_ascii=False)

    workdir = args.get("workdir", ".")
    allowed_tools = args.get("allowed_tools")
    danger_skip_permissions = args.get("danger_skip_permissions", True)
    timeout = int(args.get("timeout", 300))

    try:
        res = runner.execute_claude(
            prompt=prompt,
            workdir=workdir,
            allowed_tools=allowed_tools,
            danger_skip_permissions=danger_skip_permissions,
            timeout=timeout,
        )
        return json.dumps(res, ensure_ascii=False)
    except Exception as exc:
        logger.exception("Unexpected error in claude_code_exec")
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def handle_codex_exec(args: dict[str, Any], **kwargs: Any) -> str:
    """Tool handler for codex_exec."""
    prompt = args.get("prompt", "").strip()
    if not prompt:
        return json.dumps({"success": False, "error": "Parameter 'prompt' is required."}, ensure_ascii=False)

    workdir = args.get("workdir", ".")
    sandbox = args.get("sandbox", "workspace-write")
    timeout = int(args.get("timeout", 300))

    try:
        res = runner.execute_codex(
            prompt=prompt,
            workdir=workdir,
            sandbox=sandbox,
            timeout=timeout,
        )
        return json.dumps(res, ensure_ascii=False)
    except Exception as exc:
        logger.exception("Unexpected error in codex_exec")
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def handle_claude_slash(raw_args: str) -> str:
    """Slash command handler: /claude <prompt>."""
    prompt = raw_args.strip()
    if not prompt:
        return "用法: /claude <任务要求>\n示例: /claude 审查当前项目的单元测试并补充缺失用例"

    res = runner.execute_claude(prompt=prompt)
    if not res.get("success"):
        return f"❌ Claude Code 执行失败: {res.get('error')}\n\n输出:\n{res.get('output', '')}"

    diff_stat = res.get("diff_stat", "无文件变更")
    files = res.get("files_changed", [])
    files_str = ", ".join(files) if files else "无"

    return (
        f"✅ Claude Code 执行完成 (耗时 {res.get('duration_s', 0)}s)\n"
        f"变更文件: {files_str}\n"
        f"Diff 统计:\n{diff_stat}\n\n"
        f"执行摘要/输出:\n{res.get('output', '')}"
    )


def handle_codex_slash(raw_args: str) -> str:
    """Slash command handler: /codex <prompt>."""
    prompt = raw_args.strip()
    if not prompt:
        return "用法: /codex <任务要求>\n示例: /codex 重构 auth 模块并运行单测"

    res = runner.execute_codex(prompt=prompt)
    if not res.get("success"):
        return f"❌ Codex 执行失败: {res.get('error')}\n\n输出:\n{res.get('output', '')}"

    diff_stat = res.get("diff_stat", "无文件变更")
    files = res.get("files_changed", [])
    files_str = ", ".join(files) if files else "无"

    return (
        f"✅ Codex 执行完成 (耗时 {res.get('duration_s', 0)}s)\n"
        f"变更文件: {files_str}\n"
        f"Diff 统计:\n{diff_stat}\n\n"
        f"执行摘要/输出:\n{res.get('output', '')}"
    )


def register(ctx: Any) -> None:
    """Register tools and slash commands into Hermes."""
    # Register tools
    ctx.register_tool(
        name="claude_code_exec",
        toolset="external-agents",
        schema=schemas.CLAUDE_CODE_EXEC,
        handler=handle_claude_code_exec,
    )
    ctx.register_tool(
        name="codex_exec",
        toolset="external-agents",
        schema=schemas.CODEX_EXEC,
        handler=handle_codex_exec,
    )

    # Register slash commands
    ctx.register_command(
        name="claude",
        handler=handle_claude_slash,
        description="委托任务给 Claude Code CLI 执行并返回 Git 审计",
        args_hint="<prompt>",
    )
    ctx.register_command(
        name="codex",
        handler=handle_codex_slash,
        description="委托任务给 OpenAI Codex CLI 执行并返回 Git 审计",
        args_hint="<prompt>",
    )
