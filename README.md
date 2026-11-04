# Local Agent Configs

Sanitized backup of this machine's local AI Agent configurations.

Each Agent maintains its own dedicated subfolder to keep configurations cleanly isolated and manageable.

## Hindsight 可视化初始化

新客户端首次接入可使用 [Hindsight 初始化应用](apps/hindsight-initializer/README.md)：

- Windows 默认独立 EXE 窗口，也支持浏览器模式；Linux 使用本机网页。
- 配置远端地址、Bank 和访问令牌；选择 Codex、Claude Code、Hermes 的历史会话和文档目录。
- 本地扫描、凭据预检后，明确确认上传原件到服务端准备区；服务端解析、LLM 压缩与核验，预览后再次确认入库。
- 备份并注册所选智能体的 MCP；不覆盖现有实时钩子，不删除远端原文。
- 运行数据与凭据留在客户端，编译产物不纳入源码仓库。Windows 构建仍需真机验收。

架构、与模板恢复/双机交接的区别见 [接入说明](docs/hindsight-initializer.md)。
源码构建（Go 1.26）：

```bash
bash apps/hindsight-initializer/build.sh
```

产物输出到仓库的 `output/hindsight-initializer/`，无需更改现有恢复脚本。

## Hindsight 日常会话与访问控制

[apps/hindsight-session-ingest](apps/hindsight-session-ingest/README.md) 收录日常钩子和服务端代码：提示提交前召回，回合结束一次上传会话和变化产物，服务端清洗会话、解析并经 LLM 压缩产物后入库。
访问网关统一负责控制台登录、账号与令牌、数据仓权限和 API 鉴权开关。恢复 Codex/Claude 配置时一并安装钩子依赖，不上传真实连接配置、凭据或任务数据库。
源码推送不代表其他电脑上的客户端、初始化程序已经升级，需在各终端重新安装。

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
├── apps/
│   └── hindsight-initializer/ # Windows/Web 初始化应用、扫描压缩、MCP 接入
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
├── hermes/             # Hermes Agent configurations
│   ├── config.yaml
│   ├── SOUL.md
│   ├── memories/
│   └── plugins/        # custom non-memory plugins; Hindsight installed from catalog
├── codex/              # OpenAI Codex CLI configurations
│   ├── config.toml     # Sanitized config (proxy, providers)
│   ├── instructions.md # Memory context and prompt guidelines
│   └── hooks.json      # Hindsight recall / retain hooks
└── scripts/            # Restore and environment maintenance tools
    ├── restore_to_claude.sh
    ├── restore_to_hermes.sh  # 脱敏模板恢复，不用于双机交接
    ├── hermes_handoff.py     # 双机加密交接：init / depart / arrive / status / doctor
    ├── requirements-handoff.txt
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

The handoff tool is a separate, opt-in exception for **authenticated-encrypted snapshots** in `handoff/<lane>/latest.enc`; raw databases, live credentials and local handoff keys are never committed. Existing sanitized archives remain unchanged.

---

## One-Click Restore Commands

- **Claude Code**: `./scripts/restore_to_claude.sh`
- **Hermes 脱敏模板**: `./scripts/restore_to_hermes.sh`（会整体覆盖配置，执行前必须审查；不作为双机到达入口）。
- **Hermes 双机交接**: 按 [交接指南](docs/hermes-handoff.md) 使用 `scripts/hermes_handoff.py`。测试覆盖与未启用项见 [验证报告](docs/hermes-handoff-verification.md)。
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
