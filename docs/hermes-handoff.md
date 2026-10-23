# Hermes 双机交接：公司 → 家里 → 公司

> 明确触发，不靠自动猜测：离开机器执行 `depart`，接管机器执行 `arrive`。
> 本工具用于**同一使用者两台电脑轮流写入**，不是多人同时编辑的同步系统。
> 当前支持 Linux / WSL；Windows 用户在 WSL 内运行。无需安装后台服务、网卡驱动或桌面快捷方式。

## 先读三条底线

1. 公司记录、源代码、工具结果可能属于公司资产。必须先获得允许外传和在家处理的授权。私有 Git 和加密都不能替代该授权。
2. 一次只有一台机器写入。出发前完成任务和记忆提炼，关闭相应 Hermes 会话、Desktop 后端、Gateway 与定时写入任务；工具遇到活动进程会拒绝操作，不会自动杀进程。
3. 解密密钥只保存在两台机器本地，通过获准的安全渠道转交。不得写入 Git、聊天、日志或命令行参数值。丢失密钥无法从 Git 恢复聊天内容。

## 初次安装：两台都执行

执行目录：本仓库根目录。先正常 clone 本仓库；仓库地址由使用者自行选择获准的私有 Git 服务。

创建独立虚拟环境，不修改系统 Python：

```bash
python3 -m venv .venv-handoff
```

安装工具依赖：

```bash
.venv-handoff/bin/python -m pip install -r scripts/requirements-handoff.txt
```

查看帮助：

```bash
.venv-handoff/bin/python scripts/hermes_handoff.py --help
```

检查当前机器与仓库：

```bash
.venv-handoff/bin/python scripts/hermes_handoff.py doctor
```

不在仓库根目录执行时，可以使用脚本的绝对路径；仓库默认从脚本位置发现。通过 `--repo` 显式指定其他交接仓库。

## 公司电脑：初始化并首次出发

选定一个不含路径、姓名、IP 的设备别名，例如 `company`：

```bash
.venv-handoff/bin/python scripts/hermes_handoff.py init --device company
```

`--home` 指向 Hermes 根目录；默认 `--lane default` 使用根目录本身。`--lane work` 明确选择 `<home>/profiles/work`，不是任意标签。若 `HERMES_HOME` 已经指向某个 Profile，可直接保留 `--lane default`。**不会自动处理其他 Profile**。

```bash
.venv-handoff/bin/python scripts/hermes_handoff.py --home /path/to/hermes-home --lane work init --device company
```

工具创建本地密钥文件并仅显示文件路径。将该文件通过获准的 SSH/SFTP 或其他安全渠道传给家里电脑；不在本指南写入任何真实密钥。

完成任务，等待后台记忆提炼结束，关闭会写当前 Profile 的 Hermes。确保 Git 工作树干净、相关改动已由使用者审查并提交。首次建立交接链：

```bash
.venv-handoff/bin/python scripts/hermes_handoff.py depart --bootstrap --publish
```

`--bootstrap` 只用于第一次创建交接链；不是强制覆盖开关。

`--publish` 是**明确的提交与推送授权**：先核对远端、只接受快进，再导出加密包、追加 `ITERATION.md`、只提交交接文件并推送。脏工作树、暂存区有其他内容、未发布的旧提交、远端分叉均阻断。工具不做 `git add -A`、force push 或 hard reset。

没有 `--publish` 时只生成本地交接包，不联网、不提交、不推送。这样生成的包**还没有交付另一台机器**，需要使用者审查后手动提交和推送。

## 家里电脑：第一次接管

家里安装好 Hermes 和 cc-switch，完成本机模型接入、登录与项目路径配置；工具不会帮你复制公司的凭据。

使用安全渠道收到的密钥文件初始化：

```bash
.venv-handoff/bin/python scripts/hermes_handoff.py init --device home --key-file /path/to/private-key-file
```

导入文件必须是普通私有文件。完成初始化后可以自行妥善清理中转副本，保留工具创建的本地密钥；不要提交密钥。

关闭家里会写目标 Profile 的 Hermes；先保证本仓库干净，再首次接管：

```bash
.venv-handoff/bin/python scripts/hermes_handoff.py arrive --bootstrap --pull
```

第一次接管可能替换家里原有的聊天和共享规则，必须显式指定 `--bootstrap`；工具会先生成本地备份。**不会把两套聊天数据库自动合并**。若家里旧聊天还需要独立使用，应先使用另一个 Profile 保留。

成功后重新启动 Hermes，打开或恢复原会话继续工作。本机 `.env`、OAuth 登录、cc-switch 激活、模型路由、MCP 地址、终端目录保持本机设置。

## 后续每天只记两个命令

### 离开当前机器：出发

先完成任务、等待写入结束、关闭 Hermes，并确保仓库干净，然后：

```bash
.venv-handoff/bin/python scripts/hermes_handoff.py depart --publish
```

看到成功且确认推送完成后，当前机器已交出状态，不应继续聊天或启动会写入的后台任务。

### 换到另一台机器：到达

先关闭目标 Hermes、确认没有需要保留的未交接记录，然后：

```bash
.venv-handoff/bin/python scripts/hermes_handoff.py arrive --pull
```

成功后再启动 Hermes。**只做 `git pull` 不会恢复运行目录**；必须执行 `arrive`。

### 随时查看

```bash
.venv-handoff/bin/python scripts/hermes_handoff.py status
```

状态和诊断只显示交接元数据，不显示聊天正文、密钥或凭据。

## 什么会同步？

| 内容 | 处理方式 |
|---|---|
| 当前 Profile 的 `SOUL.md` | 加密包中同步 |
| `memories/MEMORY.md`、`memories/USER.md` | 加密包中同步 |
| `skills/`、`references/` 普通文件 | 加密包中同步，跳过符号链接与常见运行时/凭据文件 |
| `config.yaml` 的受控行为字段 | 导出白名单，恢复时合并，不整体覆盖 |
| 当前 Profile 的 `state.db` | SQLite Backup API 一致性快照，恢复前完整性校验 |
| `.env`、`auth.json`、模型 Key、OAuth、浏览器登录数据 | 不导出 |
| 模型/provider、cc-switch、MCP、terminal 路径、代理、hooks | 不覆盖，保留本机配置 |
| 其他 Profile、cron、插件运行时、锁、PID、缓存、日志 | 不同步 |
| `sessions/` 请求转储和旧镜像 | 不同步，以 `state.db` 为会话主存储 |
| 项目代码、附件、输出文件 | 不自动同步，需对应项目仓库或获准文件同步渠道 |
| MemoryCore 数据库 | 不同步；同租户服务可直接共享，独立服务需另行迁移 |

白名单以脚本实际实现为准，详情见 `--help` 与源码中的配置字段表。不是所有设置都可跨机器直接搬用。

聊天历史中引用的绝对路径、附件路径、项目工作目录**不会被自动改写**。如果公司和家里的路径不同，需要本机重新定位项目；不存在的附件不会凭空恢复。项目代码也要单独拉取对应仓库。

## 交接数据布局

```text
仓库/
├── scripts/hermes_handoff.py      # 命令入口
├── scripts/requirements-handoff.txt
├── tests/test_hermes_handoff.py   # 隔离环境的回归测试
├── docs/hermes-handoff.md         # 本指南
└── handoff/<lane>/
    ├── head.json                 # 交接代次、来源别名、密文校验值等
    └── latest.enc                # 认证加密包；没有明文聊天数据库
```

本地密钥、receipt、锁与恢复前备份在当前 Hermes home 的 `.handoff/` 下，不进 Git。目录权限收紧为 700，敏感文件权限为 600。

加密包只抵御没有密钥的人读取或篡改包。持有密钥的人可以解密全部交接内容；`SOUL.md`、技能脚本等属于可执行/高信任输入，只应接收可信本人产生的交接包。自动恢复不是对未知仓库内容的安全沙箱。

## 工具怎样避免覆盖昨天的记录？

- 每包有唯一交接代次和父代次，本机保存最后接管/交出的代次。
- 出发后本机标记 `departed`；到达成功后目标标记 `active`。
- 出发要求本机持有最新状态；到达要求父代次衔接。
- 到达前检查共享文件、受控配置与数据库逻辑内容有没有本地变化。出发后又新增记录，会拒绝覆盖。
- 数据库逻辑校验不依赖 WAL 或 checkpoint 是否变化，避免单纯落盘引发误报。
- 错密钥、包被改动、危险路径、活动进程、Git 分叉均阻断。
- 同代次重复到达不覆盖本机已经继续产生的记录。

这是交接协议，**不是跨网络的全局锁**。无法阻止你绕过工具在已交出的机器上启动 Hermes，但能在后续交接时检测变化并阻断覆盖。不能依赖两端断网时实现实时互斥。

## 故障处理

### 提示有运行中的 Hermes

在外部终端处理：结束对应聊天，退出会话后台；如有 Gateway/cron，先按你部署时的方式正常暂停。工具不会杀进程；不要强行覆盖活动数据库。

### 提示仓库脏、有旧提交或发生分叉

先查看 `git status`，由使用者审查和处理自己的改动。不要用 reset/force push 解决交接。工具不会替你把无关代码提交或推送。

### 出发时推送失败

**没有完成远端交付**。保留本地包与 receipt，不在另一台启动工作。根据命令输出检查网络及分支状态，审查工具产生的交接提交，再执行 `depart --publish` 显式重试；工具只重试原交接提交、不生成新包，并读回远端确认后更新 pending 标记。不要重复 bootstrap 或删除 receipt 重建链。

### 出发后又在旧电脑聊天

工具拒绝静默覆盖。先保留两边备份，再人工确定哪一边为主；其他新增会话需单独保留或用经过验证的导入流程处理。没有通用 SQLite 文本合并，也不提供危险的 `--force`。

### 第一次接管或版本不兼容

首次接管使用 `--bootstrap`，不要在正常交接时反复加它。建议两台保持相同 Hermes 版本；新版本写入后的数据库不应交给不兼容的旧版本。工具不自动升级 Hermes。

### 密钥丢失

无法解密仓库中的历史包。先找本机安全备份或另一台电脑的密钥。密钥更换需要另行设计迁移流程，不可仅重新初始化覆盖旧 key。

### 回滚

恢复前会保留本地备份。关闭目标 Hermes后，先检查备份和目标状态再选择恢复；不要把旧包直接覆盖到仍在运行的目录。备份可能包含本机敏感配置，仅限本地私有存储。

## 仓库体积与保留策略

会话和技能打包后属于二进制，Git 历史会持续积累。展开内容上限 512 MiB、文件数上限 5000；打包使用内存，大库需足够内存与本地备份空间。这个上限不代表 Git 服务允许同样大的单文件，首次导出应核对 `latest.enc` 大小和服务限制。长期应定期评估体积，转为获准的加密备份存储或合适的 LFS。不要擅自改写历史或删备份。工具不会自动删除旧提交中的包。

原有 `hermes/` 是脱敏配置归档，不是新交接包。旧 `scripts/restore_to_hermes.sh` 会整体覆盖配置，**不能作为双机到达入口**。现有仓库历史中原本就存在的明文归档，不会因新增加密交接工具而自动消失。

## 回归测试

在仓库根目录运行：

```bash
.venv-handoff/bin/python -m unittest discover -s tests -p 'test_hermes_handoff.py' -v
```

测试只使用临时 Hermes homes、本地 bare Git remote 和假的聊天/凭据，不触碰真实会话、真正远端或生产服务。
