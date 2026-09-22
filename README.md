# Local Agent Configs

Sanitized backup of this machine's local Agent configurations (Hermes & Claude Code).

## Contents

### 1. Hermes Configs
- `config.yaml` — sanitized root Hermes config.
- `SOUL.md` — default General Multi-Agent Router prompt.
- `memories/` — sanitized durable memory/user profile markdown.
- `profiles/<role>/config.yaml` and `SOUL.md` — SDLC role profile configs/prompts.
- `PROFILE_LIST.txt` — profile inventory from `hermes profile list`.
- `references/sdlc-role-profiles.md` — role profile reference.
- `.env.example` — env variable names only, all values redacted.
- `scripts/restore_to_hermes.sh` — conservative restore script for Hermes.

### 2. Claude Code Configs (`claude/`)
- `claude/settings.json` — 全局环境、代理网关 (172.20.0.1:7890)、mcore MCP 与思考配置。
- `claude/settings.local.json` — 本地权限白名单配置。
- `claude/config.json` — 更新状态与主 API Key 标头。
- `claude/CLAUDE.md` — 全局行为守则与透明度规范。
- `claude/installed_plugins.json` / `known_marketplaces.json` — 插件市场与已装插件清单。
- `claude/rules/common/` — 通用架构、编码规范、性能、Git 与安全等规则集。
- `claude/rules/typescript/` — TypeScript 专用规则集。
- `claude/scripts/statusline.sh` — 状态栏脚本。
- `scripts/restore_to_claude.sh` — 一键恢复 Claude Code 配置至 `~/.claude/`。

## Security policy

This repo intentionally excludes live secrets and runtime state: `.env`, `auth.json`, OAuth tokens, sessions, logs, caches, SQLite state, and venvs. Any secret-like values in YAML/Markdown/JSON are replaced with `<REDACTED>` or placeholder identifiers.

## Restore

- **Hermes**: `./scripts/restore_to_hermes.sh`
- **Claude Code**: `./scripts/restore_to_claude.sh`
