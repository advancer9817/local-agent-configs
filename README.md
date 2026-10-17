# Local Agent Configs

Sanitized backup of this machine's local AI Agent configurations.

Each Agent maintains its own dedicated subfolder to keep configurations cleanly isolated and manageable.

## Hermes 公司 / 家里双机交接

**先读：[完整使用指南](docs/hermes-handoff.md)。**

明确触发：离开电脑执行 `depart`，换到另一台执行 `arrive`，不是单纯 `git pull` 后自动覆盖运行目录。

- 初始化：`python3 scripts/hermes_handoff.py init --device company`（另一台用 `--device home --key-file 私有密钥文件路径`）。
- 离开电脑：`python3 scripts/hermes_handoff.py depart --publish`。
- 接管电脑：`python3 scripts/hermes_handoff.py arrive --pull`。
- 检查状态：`python3 scripts/hermes_handoff.py status`。
- 首次建立链或首次接管需显式 `--bootstrap`；依赖安装、离线要求和完整命令见指南。

使用独立 venv 中的 Python，以上 `python3` 为入口示意。**关闭会写目标 Profile 的 Hermes 后再出发/到达；不在当前活动会话里覆盖自己的数据库。**

规则、记忆、技能和会话快照统一认证加密；仅受控行为配置跨机合并。本机 Key、cc-switch、OAuth、MCP 地址与路径不覆盖。默认不联网，只有 `--publish` 明确提交推送，`--pull` 明确拉取。公司数据需先获准外传。

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
    ├── restore_to_hermes.sh  # 脱敏模板恢复，不用于双机交接
    ├── hermes_handoff.py     # 双机加密交接：init / depart / arrive / status / doctor
    ├── requirements-handoff.txt
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

The handoff tool is a separate, opt-in exception for **authenticated-encrypted snapshots** in `handoff/<lane>/latest.enc`; raw databases, live credentials and local handoff keys are never committed. Existing sanitized archives remain unchanged.

---

## One-Click Restore Commands

- **Claude Code**: `./scripts/restore_to_claude.sh`
- **Hermes 脱敏模板**: `./scripts/restore_to_hermes.sh`（会整体覆盖配置，执行前必须审查；不作为双机到达入口）。
- **Hermes 双机交接**: 按 [交接指南](docs/hermes-handoff.md) 使用 `scripts/hermes_handoff.py`。测试覆盖与未启用项见 [验证报告](docs/hermes-handoff-verification.md)。
- **Codex**: `./scripts/restore_to_codex.sh`
