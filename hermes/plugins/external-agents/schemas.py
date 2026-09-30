"""Tool schemas for external-agents plugin."""

CLAUDE_CODE_EXEC = {
    "name": "claude_code_exec",
    "description": (
        "Delegate coding, debugging, refactoring, or review tasks to Claude Code CLI in non-interactive print mode. "
        "Executes directly in the target workspace, captures execution output, and returns audit metrics including changed files and git diff."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Task instructions and technical requirements for Claude Code.",
            },
            "workdir": {
                "type": "string",
                "description": "Working directory path where Claude Code should operate. Defaults to current working directory.",
            },
            "allowed_tools": {
                "type": "string",
                "description": "Comma-separated list of allowed tools (e.g. 'Read,Edit,Bash'). If omitted, all standard tools are allowed.",
            },
            "danger_skip_permissions": {
                "type": "boolean",
                "description": "Whether to pass --dangerously-skip-permissions to bypass non-interactive permission prompts. Defaults to true.",
                "default": True,
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds. Defaults to 300.",
                "default": 300,
            },
        },
        "required": ["prompt"],
    },
}

CODEX_EXEC = {
    "name": "codex_exec",
    "description": (
        "Delegate implementation, refactoring, or review tasks to OpenAI Codex CLI in non-interactive exec mode. "
        "Executes directly in the target git workspace, captures execution output, and returns audit metrics including changed files and git diff."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Task instructions and technical requirements for Codex.",
            },
            "workdir": {
                "type": "string",
                "description": "Working directory path where Codex should operate (must be a git repository). Defaults to current working directory.",
            },
            "sandbox": {
                "type": "string",
                "description": "Sandbox mode for Codex. Choices: 'workspace-write', 'danger-full-access', 'read-only'. Defaults to 'workspace-write'.",
                "enum": ["workspace-write", "danger-full-access", "read-only"],
                "default": "workspace-write",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds. Defaults to 300.",
                "default": 300,
            },
        },
        "required": ["prompt"],
    },
}
