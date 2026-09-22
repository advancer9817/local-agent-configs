# Local Agent Configs

Sanitized backup of this machine's local AI Agent configurations.

Each Agent maintains its own dedicated subfolder to keep configurations cleanly isolated and manageable.

---

## Directory Structure

```text
local-agent-configs/
├── claude/             # Claude Code configurations & rules
│   ├── CLAUDE.md
│   ├── settings.json
│   ├── settings.local.json
│   ├── config.json
│   ├── installed_plugins.json
│   ├── known_marketplaces.json
│   ├── rules/          # common/ & typescript/ rule sets
│   ├── scripts/        # statusline.sh
│   └── plugins_archive/
├── hermes/             # Hermes Agent configurations & profiles
│   ├── config.yaml
│   ├── SOUL.md
│   ├── PROFILE_LIST.txt
│   ├── memories/
│   ├── profiles/       # SDLC role profiles
│   ├── references/
│   └── plugins/        # mcore-memory plugin
├── codex/              # OpenAI Codex CLI configurations
│   ├── config.toml     # Sanitized config (proxy, providers)
│   ├── instructions.md # Memory context and prompt guidelines
│   └── hooks.json      # Session hooks for mcore
└── scripts/            # Restore and environment maintenance tools
    ├── restore_to_claude.sh
    ├── restore_to_hermes.sh
    ├── restore_to_codex.sh
    ├── mcore-context.sh
    ├── mcore-ingest.py
    └── cc-switch-wslg-fix/
```

---

## Security Policy

This repo intentionally excludes live secrets, auth tokens, database files, and runtime state:
- `.env`, `auth.json`, OAuth tokens, session keys
- SQLite files (`*.sqlite`, `*.db`)
- Logs, caches, temporary files, and venvs

All sensitive tokens are replaced with `<REDACTED>` placeholders.

---

## One-Click Restore Commands

- **Claude Code**: `./scripts/restore_to_claude.sh`
- **Hermes**: `./scripts/restore_to_hermes.sh`
- **Codex**: `./scripts/restore_to_codex.sh`
