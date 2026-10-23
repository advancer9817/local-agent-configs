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
│   └── plugins/        # custom non-memory plugins; Hindsight installed from catalog
├── codex/              # OpenAI Codex CLI configurations
│   ├── config.toml     # Sanitized config (proxy, providers)
│   ├── instructions.md # Memory context and prompt guidelines
│   └── hooks.json      # Hindsight recall / retain hooks
└── scripts/            # Restore and environment maintenance tools
    ├── restore_to_claude.sh
    ├── restore_to_hermes.sh
    ├── restore_to_codex.sh
    ├── hindsight-hook.py
    ├── start-hindsight-tunnels.py
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


## 可移植路径约定

- 配置模板中的 `./` 以**目标用户 HOME**为基准，不是启动命令的工作目录。恢复脚本会将 JSON、YAML、TOML 中的路径解析为目标机器的实际路径；不要直接复制模板替代恢复步骤。
- 从任意目录执行仓库的 `scripts/restore_to_<agent>.sh`；可传 `--home <目标用户目录>` 和 `--target <配置目录>`。例如在仓库根目录执行 `./scripts/restore_to_codex.sh --home "$HOME"`。
- 恢复工具需要 Python 3.11+；Hermes YAML 恢复额外需要 PyYAML。使用 `PYTHON` 选择解释器。恢复前备份被覆盖文件，凭据不会从仓库恢复。
- Windows 用户目录与系统工具由平台发现；WSL 下可用 `WINDOWS_USER_HOME`、`WINDOWS_SYSTEM_ROOT` 显式指定。脚本从自身位置确定仓库根目录，不再绑定用户名或工程目录。
- 服务 IP、API URL、系统规定路径（解释器 shebang、系统库、设备路径）不是个人文件地址，不作相对化。`ITERATION.md` 与历史报告保留当时的真实路径；不重写历史。
- Codex 项目信任记录、Hook 授权哈希和 Hermes 安装更新状态属于单机运行状态，不随模板分发；部署后由客户端重新建立。
- Hindsight 接入不再强制本机回环或 SSH；保留可选工具不表示要求自动启动隧道。本次只调整规则与仓库路径，不迁移运行中客户端的连接地址。
- `scripts/migrate-hindsight-local.py`、`finish-hindsight-migration.py` 为历史迁移工具，会修改真实客户端，不能拿来代替隔离恢复测试。
