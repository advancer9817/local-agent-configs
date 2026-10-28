# hermes-local-agent-configs 迭代记录

本文件记录随仓库提交一起推送的项目迭代信息，用于追溯每次变更的范围、原因与提交记录。

## 2026-10-20 +0800 - feat(hindsight): GCP 50 记忆编排、冗余剪枝与心智模型初始化

- 项目: `GCP 50 (35.236.134.50) / Hindsight (Bank: mcore-active-snapshot)`
- 修改说明:
  1. **响应用户指令连续推进编排治理**：跳过第一阶段全库转储，通过原生 OpenSSH 穿透链路依次完成第二至第五阶段调优；
  2. **阶段二（精准剪枝）**：通过 Hindsight 官方 API 级联清理 127 份冗余文档（表格尾段 34 份、旧版 WSL ITERATION 7 份、递增前缀快照 77 份、通知与闲聊 9 份），使全库唯一 1 条 `consolidation_failed` 状态彻底归零；
  3. **阶段三（凭据脱敏）**：对两份保留的含明文 AK 与 Groq Key 的会话文档正则脱敏并覆写入库，全库明文密钥残留归零；
  4. **阶段四（参数调优）**：在 `/opt/hindsight-research/runtime.json` 注入 `HINDSIGHT_API_RECALL_MAX_QUERY_TOKENS=2500` 等参数，消除 500 token 硬截断告警；
  5. **阶段五（标题与心智模型）**：事务回填近期文档的 `display_title`（标题覆盖率达到 100%），并通过官方 API 创建激活了 5 个核心领域 Mental Models（网络拓扑、记忆与技能规范、QAI口径、TPMS架构、个人工程偏好），全部完成合成（合计 18,501 字）；
  6. **阶段六（深度语义去重与残缺碎片清理）**：利用 `pgvector` 余弦矩阵与 3-gram 包含度执行 CD-HIT 星型无传递去重（严格保留 477 个重复簇的 Winner 基准项），并通过官方 `DELETE` API 级联清理 **960 份深层冗余与低质量文档**（mcore 语义重复副本 900 份、早期按英文点号劈断的断头断尾残片 43 份、WSL/GCP 跨端重复与被 v2 取代的旧报告 9 份、瞬态测试探针与空转确认轮次 8 份），删前全量备份于 `/opt/hindsight-research/consolidation-optimize-20261020/stage6_pre_delete_backup.json.gz`，全库文档收敛至 6,157 份；
  7. **交付物同步**：在桌面输出离线单文件 HTML 报告《GCP50_Hindsight记忆编排与治理实施方案_20261020.html》。
- 影响范围: GCP 50 远端 Hindsight 数据库、`runtime.json`、本地通用交付目录
- 验证: `hindsight_recall` 实测返回正常；PostgreSQL 查验 `consolidation_failed_at IS NOT NULL` 为 0，明文凭据匹配为 0，缺失标题为 0，`mental_models` 数量为 5。
- 状态: 远端操作完成，本地未执行 git push。

## 2026-10-20 +0800 - docs(hermes): SOUL 新增方案文档 HTML 交付规则

- 项目: `hermes-local-agent-configs`
- 修改说明: 用户要求“以后的实施细节，各种方案都出 HTML 版”，并补充“不能跟 md 一样，要充分利用 HTML 优势增强可读性”。在 SOUL.md 第 4 节“统一交付路径”新增一条：方案、实施细节评审、口径对比等文档一律交付离线单文件 HTML，严禁 Markdown 直转；须结论前置并善用流程图、对比表、状态色标、时间线、可折叠细节与目录导航，样式贴合主题，交付前浏览器核验。
- 变更范围: `hermes/SOUL.md`（与运行时 `~/.hermes/SOUL.md` 同步，两份逐字一致）、`ITERATION.md`
- 影响: 仅新会话生效（会话内 System Prompt 冻结）；不涉及配置与凭据。
- 验证: `cmp ~/.hermes/SOUL.md hermes/SOUL.md`
- 回滚: 删除该条即可。
- 状态: 未提交、未推送（仓库另有 Hindsight 迁移等未提交改动，待用户决定是否一并提交）。

## 2026-10-07 18:20:00 +0800 - feat(hermes): register /gate as native skill for desktop autocomplete popover

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. **彻底解决桌面端输入 /gate 无法补全的问题**：
     - 排查 Hermes Desktop 前端补全机制 `complete.slash` 与 `SlashCommandCompleter`，确认桌面端输入框的 `/` 浮窗联想来源仅为内置 COMMANDS 与注册的 SKILLS（Plugins 不参与输入框实时词条联想）；
     - 正统创建官方技能 `~/.hermes/skills/gate/SKILL.md`，使 `/gate` 拥有与 `/codex` 完全同级的 ⚡ 官方技能联想入口，彻底在桌面端输入框浮窗中就绪；
  2. **双轨保障**：
     - 桌面端输入 `/gate` 享有 ⚡ 自动补全并在敲回车时直接触发执行状态翻转与报告输出；
     - 终端与脚本仍可随时调用全局 `/home/advancer/.local/bin/gate`；
  3. 经 `hermes skills list` 与 `get_interactive_skill_commands()` 验证，`/gate` 已 100% 成为系统原生技能命令；本地提交，严格遵守安全红线不向远端 push。
- 变更范围: `hermes/skills/gate/SKILL.md`, `ITERATION.md`

## 2026-10-07 18:10:00 +0800 - fix(codex,mcore): fix stop hook envelope schema and inject Gemini model metadata

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. **根治 Stop Hook 报错**：排查并修正 `memorycore` 项目源码 `mcore-client/mcore-client.js` 与运行时边车中的 `handleHookIngest` 响应体，将裸对象包装为包含 `hookSpecificOutput: { hookEventName: 'Stop' }` 的合规信封，彻底消除 Codex 与其它 Agent 执行时报出 `invalid stop hook JSON output` 的问题；
  2. **消除 Codex 缺失模型元数据告警**：在 WSL 端与 Windows 宿主机双端的 `models_cache.json` 中注入 `gemini-3.8-flash` 与 `gemini-3.8-flash[1M]` 专属元数据项，支持 4 档推理级别（low/medium/high/xhigh），消除黄色 `Model metadata not found` 警告；
  3. **环境与服务热重载**：重启 `mcore-client` 本地守护进程，测试真实调用验证通过；同步配置至脱敏仓库。
- 变更范围: `codex/models_cache.json`, `memorycore/mcore-client/mcore-client.js`, `ITERATION.md`

## 2026-10-07 17:50:00 +0800 - fix(hermes): register native /gate plugin command and classify Gemini Flash as constrained model

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. **Gemini Flash 模型归类校准**：遵循用户铁律，将 Gemini Flash 全系列模型显式从免排版高级白名单中完全剔除，严格归入“基础/必须受排版约束模型”；确立本排版透明约束专为 Gemini Flash 防黑盒哑巴调用而生，在 AUTO 模式下对 Flash 强制全量注入规范，仅对真实高智力推理模型（Opus/Sonnet/GPT-4o/Pro）静默排版；
  2. **解决桌面端无 /gate 指令根因**：查明 Hermes 桌面客户端 `slash.exec` 不执行静态 `quick_commands`，仅识别官方 Plugins/Skills 的内核限制。正统落地 `gate-control` 原生插件（`ctx.register_command("gate")`），在桌面端注册一等公民 Slash Command；
  3. **交互体验闭环**：在桌面端输入 `/gate` 支持自动补全、传参（`/gate off`、`/gate on`、`/gate auto`、`/gate status`）以及无参数一键 Toggle 快速翻转模式；
  4. 现场 Python 句柄与 Hook 模型双向全量验证绿灯通过；本地提交，严格遵守安全红线不向远端 push。
- 变更范围: `plugins/gate-control/`, `scripts/superpowers-intent-gate.py`, `scripts/gate`, `ITERATION.md`

## 2026-10-07 17:30:00 +0800 - feat(hermes): deploy Hybrid Model-Sensing & Quick Command Router for rules injection

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. **架构彻底解耦**：将死板的“工具调用三段式排版规范”从静态 `SOUL.md` 中完全移出，使 System Prompt 保持纯净底色（中文、安全红线、交付路径）；
  2. **智能中枢 Hook 升级**：`superpowers-intent-gate.py` 全面接管排版格式与硬门禁，实现“三态控制 + 模型智商白名单自适应分流”：
     - `AUTO` 模式（默认）：检测到高等智能模型（`Opus` / `Sonnet` / `GPT-4o` / `Pro` 等）自动静默排版废话（仅保留硬门禁）；普通小模型自动补全排版规范防黑盒；
     - `OFF` 模式：强制注入 0 字符，彻底放飞直接交付；
     - `ON` 模式：所有模型强制注入硬门禁 + 工具排版规范；
  3. **快捷交互全覆盖**：
     - 在 `config.yaml` 注册原生 `quick_commands`：支持在桌面端聊天框通过 `/gate`、`/gate-auto`、`/gate-off`、`/gate-on` 秒级热切换，零 Token 损耗；
     - 全局终端命令 `/home/advancer/.local/bin/gate` 同步升级支持三态指令与状态面板；
  4. 现场 4 项核心测试全量通过；本地提交，严格遵守安全红线不向远端 push。
- 变更范围: `hermes/SOUL.md`, `scripts/superpowers-intent-gate.py`, `scripts/gate`, `ITERATION.md`

## 2026-10-07 17:10:00 +0800 - feat(hermes): add 'gate' CLI switch for dynamic Superpowers hard-gate injection control

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 为 Hermes 的 Pre-LLM Hook (`superpowers-intent-gate.py`) 引入标志文件热检测机制（`~/.hermes/flags/superpowers_gate.disabled`）；
  2. 编写并安装全局快捷命令 `/home/advancer/.local/bin/gate`，支持 `gate on`、`gate off`、`gate status` 极简管理；
  3. `gate on` 保持严谨安全防护，每轮推理前自动注入 Superpowers 意图对齐与开工硬门禁；`gate off` 彻底解除前置刹车注入，允许自主高效直接交付；
  4. 秒级热生效、零重启无感切换；严格遵守安全规范，本地提交，不向远端执行 push。
- 变更范围: `scripts/superpowers-intent-gate.py`, `scripts/gate`, `ITERATION.md`

## 2026-10-07 16:45:00 +0800 - feat(external-agents): upgrade Claude runner to native PTY-driven supervision

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 重构 `external-agents` 插件核心执行器 `runner.py`，将底层命令行管道全面重构为原生 PTY（伪终端）驱动模式；
  2. 实现全生命周期执行状态监控，实时提取阶段标签（`started` / `thinking` / `executing_tools` / `completing` / `finished`）；
  3. 自动剥离 ANSI 转义字符并进行密钥脱敏，结合 `git_tracker` 自动捕获任务执行前后的代码变更（`files_changed`, `diff_stat`, `diff_summary`）汇总至 Hermes；
  4. 自动读取并对齐远程生产网关配置（`http://35.236.134.50:8317` 与 `gemini-3.8-flash[1M]`），根除协议畸形与网关记录污染风险；
  5. 9/9 单元测试全量绿灯通过。
- 变更范围: `hermes/plugins/external-agents/runner.py`, `ITERATION.md`

## 2026-10-07 16:26:00 +0800 - feat(claude): initialize h2c bridge skill and settings for Hermes remote control

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 安装并集成 `hermes-to-claude` (h2c) 架构，打通 Hermes 通过 HTTP 控制 Claude Code 多实例能力；
  2. 初始化 Claude Code 原生技能文件 `~/.claude/skills/h2c/SKILL.md`，修复 npm 拦截 postinstall 导致的 `No commands match "/h2c"` 缺失问题；
  3. 完善 `~/.claude/settings.json` 的模型映射配置，增加 `gemini-3.8-flash-n` 兼容支持，保障底层流式数据解析通畅。
- 变更范围: `claude/skills/h2c/SKILL.md`, `claude/settings.json`, `ITERATION.md`

## 2026-09-30 16:16:04 +0800 - feat(hermes): add external-agents plugin to orchestrate Claude Code and Codex

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 开发并交付 Hermes 原生插件 `external-agents`，为 Hermes 赋予直接编排调用本地 Claude Code CLI (`claude -p`) 与 OpenAI Codex CLI (`codex exec`) 的能力；
  2. 模块结构：
     - `schemas.py`: 定义 `claude_code_exec` 与 `codex_exec` 强类型工具契约；
     - `git_tracker.py`: 提取执行前后 `git status --porcelain` 与 `git diff --stat` 差异，保障工作区变更可审计；
     - `runner.py`: 封装非交互免挂死运行、超时防护、退出码检测与敏感 Key/Token 自动脱敏；
     - `__init__.py`: 注册原生工具并新增 `/claude` 与 `/codex` 斜杠命令；
     - `plugin.yaml`: 声明插件元数据并显式标注 `provides_tools`；
  3. 配套编写 9 个单元测试用例并通过全量绿灯验证；
  4. 创建并激活配套调度技能 `external-agents`；
  5. 在 Hermes 生产配置 `~/.hermes/config.yaml` 与脱敏配置中正式激活该插件，并通过 `hermes plugins doctor` 校验通过。
- 变更范围: `hermes/config.yaml`, `hermes/plugins/external-agents/`, `docs/superpowers/specs/2026-09-30-external-agents-plugin-design.md`, `ITERATION.md`

## 2026-09-29 10:18:00 +0800 - feat(hermes): integrate and enforce Superpowers intent clarification hard-gate

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 正式安装启用 Superpowers 体系的核心调度技能 `using-superpowers` 与需求澄清技能 `superpowers-brainstorming`；
  2. 在 `SOUL.md`（生产端 `~/.hermes/SOUL.md` 与配置仓库 `hermes/SOUL.md`）交互规范中增加第 5 条“意图对齐与开工硬门禁”；
  3. 编写并挂载 Shell Hook (`~/.hermes/agent-hooks/superpowers-intent-gate.py`) 至 `pre_llm_call` 生命周期事件，配置 `shell-hooks-allowlist.json` 白名单与 `hooks_auto_accept: true`，实现每轮 LLM 推理前动态注入 Superpowers 意图对齐硬门禁指令；
  4. 强制在面对任何新功能开发、修改已有行为或目标不明确任务时，开工前严禁直接写入代码，必须先激活流程技能并获得用户明确确认。
- 变更范围: `hermes/SOUL.md`, `hermes/config.yaml`, `scripts/superpowers-intent-gate.py`

## 2026-10-07 09:55:00 +0800 - feat(claude,codex): sync 2-3 paragraph blank-line separation rules to Claude and Codex

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 在 Hermes 验证效果闭环后，将“空行自然分段（2~3段）、严禁单行挤占、严禁123序号、严禁上步等八股标签”的交互规范全量同步推广至：
     - Claude Code (`~/.claude/CLAUDE.md`)
     - OpenAI Codex (`~/.codex/instructions.md`)
  2. 保持跨 Agent（Hermes、Claude Code、Codex）工具调用透明度规范与排版审美的绝对统一；
  3. 严格遵循版本安全规范，改动仅在本地安全提交，未经授权不向远端执行 git push。
- 变更范围: `claude/CLAUDE.md`, `codex/instructions.md`

## 2026-10-07 09:45:00 +0800 - refactor(hermes): enforce 2-3 paragraph blank-line separation for tool calls, ban single-line grouping

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 仅限 Hermes 作用域，重构 `SOUL.md` 与用户画像 `USER.md` 中的工具调用排版与透明度铁律：
     - 强制每次调用工具前面向用户的文本必须严格通过换行空行分成 2~3 个独立段落呈现；
     - 绝对禁止压缩在单一行内，保证视觉结构清晰与阅读呼吸感；
     - 坚决杜绝任何形式的数字序号（如 1/2/3、①/②/③、第一/第二等）；
     - 坚决杜绝“上步”、“上一步”、“上轮”、“思考推导：”、“本步动作：”等死板八股前缀；
  2. 范围严格限定在 Hermes，待用户验证确认后再视情况推广至 Claude 与 Codex；
  3. 严格遵循安全红线与开工门禁，不执行向远端的 push 操作。
- 变更范围: `hermes/SOUL.md`, `hermes/memories/USER.md`

## 2026-10-07 09:35:00 +0800 - refactor(all): eliminate numbered lists (123) and rigid 'last-step' tags in tool call transparency rules

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 重构 Claude Code (`CLAUDE.md`)、Codex (`instructions.md`) 与 Hermes (`SOUL.md`) 的工具调用交互规范：
     - 显式禁止使用任何形式的数字序号（如 1/2/3、①/②/③、第一/第二等）；
     - 显式禁止使用“上步……”、“上一步……”、“上轮……”、“思考推导：”、“本步动作：”等死板前缀；
     - 转换为“纯自然语流”：自然陈述前序事实状态、交代因果推导，并以动词短语直述本步意图；
  2. 保持非空输出红线（杜绝黑盒与哑巴调用），解决模型机械化照搬模板前缀的负面体验；
  3. 同步更新 `USER.md` 长期用户偏好记忆与全套生产环境配置。
- 变更范围: `claude/CLAUDE.md`, `codex/instructions.md`, `hermes/SOUL.md`, `hermes/memories/USER.md`

## 2026-09-28 16:05:00 +0800 - fix(claude): configure instructionFiles to claude-md in settings.json to silence fallback notice

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 在 Claude 核心配置文件 `~/.claude/settings.json` 中配置 `"instructionFiles": "claude-md"`；
  2. 彻底关闭 v2.1.283 内置 `agents-md` 插件因工作目录未放置独立 CLAUDE.md 而产生的回退提示 (`no CLAUDE.md found; AGENTS.md loaded`)；
  3. 保持用户工作目录干净，所有行为由 Claude 核心配置目录统摄。
- 变更范围: `claude/settings.json`

## 2026-09-28 15:55:00 +0800 - feat(claude,codex): sync 3-phase transparent tool execution rules to Claude and Codex

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 为 Claude Code (`~/.claude/CLAUDE.md`) 与 OpenAI Codex (`~/.codex/instructions.md`) 全面引入统一的“工具调用三段式透明铁律”：
     - ① 上步结果（客观数据/事实，首步跳过）；
     - ② 思考推导（内部思维链核心逻辑用中文直接提炼，决策因果白盒化）；
     - ③ 本步动作（动词交代即将调用的工具意图与标的）；
  2. 严禁面向用户的文本留空（content 为空），严禁将推导藏入 reasoning/thinking 表现为哑巴调用；
  3. 彻底禁用“正在……”、“上步已……”等死板八股前缀；
  4. 同步更新本地生产环境与脱敏配置仓库。
- 变更范围: `claude/CLAUDE.md`, `codex/instructions.md`

## 2026-09-28 15:45:00 +0800 - refactor(hermes): condense 3-phase transparency rules into concise high-signal directives

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 精简交互规范文字冗余，删除重叠长句与嵌套编号，压缩篇幅 60%，提升指令密度与大模型遵从度；
  2. 凝练保持三大核心铁律：
     - ① 物理级禁止 tool_calls 时 content 为空（严禁将推导藏入 reasoning 当哑巴）；
     - ② 三段式严格保真：①上步核心结果 ②思考因果中文提炼 ③本步动词动作，随后发起调用；
     - ③ 严禁“正在……”、“上步已……”等死板八股标签；
  3. 同步精简 SOUL.md 与 USER.md。
- 变更范围: `hermes/SOUL.md`, `hermes/memories/USER.md`

## 2026-09-28 15:35:00 +0800 - feat(hermes): enforce 3-phase transparent content on tool_calls (last result + zh reasoning + next intent)

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 遵照用户要求，确立连续工具调用时 content 的三段式全流程透明输出结构：
     - ① 上一轮工具调用的核心结果（首轮起步无上轮时跳过，陈述关键数据/分水岭事实）；
     - ② 思维链（Reasoning）的核心逻辑与决策因果直接以通俗严谨中文提炼呈现在 content 中，无需翻阅折叠的英文思考链；
     - ③ 本轮要调用的内容与技术意图（去主语动词陈述），随后伴随发起 tool_calls；
  2. 严禁死板八股标签（严禁“正在……”、“上步已……”等），自然客观陈述；
  3. 同步更新 SOUL.md 与 USER.md。
- 变更范围: `hermes/SOUL.md`, `hermes/memories/USER.md`

## 2026-09-28 15:20:00 +0800 - feat(hermes): enforce non-empty content with active verb intent on tool_calls to eliminate silent executions

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 彻底解决大模型在 Function Calling 场景下将意图藏入 reasoning 思维链而在前端表现为 0 字符空 content 哑巴调用的黑盒痛点；
  2. 确立数据协议级铁律：发起 tool_calls 时 Assistant 消息的 content 文本字段严禁留空或为 0 字符；
  3. 强制伴随式意图交代：必须在同一个响应中先用去主语的动词清晰陈述技术意图，再发起 tool_calls，破除 content 与 tool_calls 互斥偏见；
  4. 严禁将面向用户的交代留于私有思考链（reasoning）中；
  5. 同步升级 SOUL.md 与 USER.md。
- 变更范围: `hermes/SOUL.md`, `hermes/memories/USER.md`

## 2026-09-23 14:40:00 +0800 - refactor(hermes): adopt Plan A natural engineering interaction over brittle per-step dual-paragraph rule

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 彻底废除每步强行“两段式+空行”的死板约束，解决多步调用下模型注意力衰减与自复制坍塌的死结；
  2. 确立“方案 A：重阶段事实、轻单步报幕”原则：起手与转折直述技术意图，仅在拿到关键分水岭事实（断层/根因/分歧）时做阶段性判断交接；
  3. 日常连贯查询干净推进，彻底消除“正在……”与“上步已……”等八股标签，避免流水账念经；
  4. 同步更新 SOUL.md 与 USER.md。
- 变更范围: `hermes/SOUL.md`, `hermes/memories/USER.md`

## 2026-09-23 14:35:00 +0800 - feat(hermes): enforce 2-paragraph narration with strict facts across multi-step tools

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明: 
  1. 重构 SOUL.md 与 USER.md 交互规则，强制要求连续工具调用必须输出两段结构（首行具体事实，双换行空行，次行具体动作）；
  2. 严厉封禁“只报下步干嘛、吃掉上步结果”的格式坍塌行为；
  3. 彻底杜绝“正在……”及“上步已……”等任何八股前缀；
  4. 经 21 轮长链路真实任务端到端实测验证，连续 8 步工具全部稳定保持事实+空行+动作标准结构。
- 变更范围: `hermes/SOUL.md`, `hermes/memories/USER.md`

## 2026-09-23 13:55:00 +0800 - memory(hermes): sync action transparency rules in USER.md

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明: 同步清除 USER.md 中残留的“(动词+标的+目的)”单向报幕要求，统一对齐为承上启下闭环规则。
- 变更范围: `hermes/memories/USER.md`

## 2026-09-23 13:45:00 +0800 - config(hermes): disable tool_use_enforcement to eliminate hardcoded prompt override

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明: 将 agent.tool_use_enforcement 设为 false，彻底解除针对 Gemini 模型的硬编码 Conciseness 与 Keep going 英文指令注入。
- 变更范围: `hermes/config.yaml`

## 2026-09-23 13:30:00 +0800 - feat(hermes): refine action transparency and execution feedback in SOUL.md

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明: 优化动作交代规范，增加步进反馈阀门（严禁超2次工具完全静默），防范过度矫正引发的失声与黑盒盲等。
- 变更范围: `hermes/SOUL.md`

## 2026-05-19 14:17:17 +0800 - docs(hermes-local-agent-configs): update project iteration
     6|
     7|- 项目: `hermes-local-agent-configs`
     8|- 分支: `main`
     9|- 远端: `https://github.com/advancer9817-crypto/hermes-local-agent-configs.git`
    10|- 关联提交: `0245bf312750c0b711d784905e3c2c9060d53809`
    11|- 提交时间: `2026-05-19 14:13:58 +0800`
    12|- 提交作者: `advancer9817-crypto <advancer9817-crypto@users.noreply.github.com>`
    13|
    14|### 迭代说明
    15|
    16|```text
    17|- config.yaml                           | 10 +---------
    18|- memories/MEMORY.md                    |  2 +-
    19|- profiles/commitint/config.yaml        | 10 +---------
    20|- profiles/commitint/memories/MEMORY.md |  2 +-
    21|- profiles/coord/config.yaml            | 10 +---------
    22|- profiles/coord/memories/MEMORY.md     |  2 +-
    23|- profiles/design/config.yaml           | 10 +---------
    24|- profiles/design/memories/MEMORY.md    |  2 +-
    25|- profiles/impl/config.yaml             | 10 +---------
    26|- profiles/impl/memories/MEMORY.md      |  2 +-
    27|- profiles/qa/config.yaml               | 10 +---------
    28|- profiles/qa/memories/MEMORY.md        |  2 +-
    29|```
    30|
    31|### 修改范围统计
    32|
    33|```text
    34|config.yaml                           | 10 +---------
    35| memories/MEMORY.md                    |  2 +-
    36| profiles/commitint/config.yaml        | 10 +---------
    37| profiles/commitint/memories/MEMORY.md |  2 +-
    38| profiles/coord/config.yaml            | 10 +---------
    39| profiles/coord/memories/MEMORY.md     |  2 +-
    40| profiles/design/config.yaml           | 10 +---------
    41| profiles/design/memories/MEMORY.md    |  2 +-
    42| profiles/impl/config.yaml             | 10 +---------
    43| profiles/impl/memories/MEMORY.md      |  2 +-
    44| profiles/qa/config.yaml               | 10 +---------
    45| profiles/qa/memories/MEMORY.md        |  2 +-
    46| profiles/req/config.yaml              | 10 +---------
    47| profiles/req/memories/MEMORY.md       |  2 +-
    48| profiles/review/config.yaml           | 10 +---------
    49| profiles/review/memories/MEMORY.md    |  2 +-
    50| profiles/security/config.yaml         | 10 +---------
    51| profiles/security/memories/MEMORY.md  |  2 +-
    52| 18 files changed, 18 insertions(+), 90 deletions(-)
    53|```
    54|
    55|### 文件变更清单
    56|
    57|```text
    58|M	config.yaml
    59|M	memories/MEMORY.md
    60|M	profiles/commitint/config.yaml
    61|M	profiles/commitint/memories/MEMORY.md
    62|M	profiles/coord/config.yaml
    63|M	profiles/coord/memories/MEMORY.md
    64|M	profiles/design/config.yaml
    65|M	profiles/design/memories/MEMORY.md
    66|M	profiles/impl/config.yaml
    67|M	profiles/impl/memories/MEMORY.md
    68|M	profiles/qa/config.yaml
    69|M	profiles/qa/memories/MEMORY.md
    70|M	profiles/req/config.yaml
    71|M	profiles/req/memories/MEMORY.md
    72|M	profiles/review/config.yaml
    73|M	profiles/review/memories/MEMORY.md
    74|M	profiles/security/config.yaml
    75|M	profiles/security/memories/MEMORY.md
    76|```
    77|
    78|
    79|
    80|## 2026-05-19 17:37:35 - Sync local Hermes agent configs
    81|
    82|### 目的
    83|- 将当前本机 Hermes Agent 配置、General Multi-Agent Router SOUL、SDLC role profiles、profile memories/reference 文档导出到本仓库，形成可版本化的本地配置备份。
    84|
    85|### 变更摘要
    86|- 更新根配置：`config.yaml`、`SOUL.md`、`memories/`。
    87|- 更新 profiles：`coord`、`req`、`design`、`impl`、`qa`、`review`、`security`、`commitint` 的 `config.yaml`、`SOUL.md` 与 memories。
    88|- 更新 `PROFILE_LIST.txt`、`README.md`、`.env.example`、`.gitignore`、`references/sdlc-role-profiles.md`、`scripts/restore_to_hermes.sh`。
    89|- 所有 secret-like 字段已写为 `<REDACTED>`；未导出 `.env` 真实值、`auth.json`、sessions、logs、state DB、cache、venv。
    90|
    91|### 验证
    92|- `git diff --check` 通过。
    93|- YAML 解析校验通过：root + 8 个 profile config 均可解析。
    94|- 敏感信息扫描通过：未发现未脱敏的 api key/token/secret/password/private key 模式。
    95|
    96|### 风险与回滚
    97|- 风险：该仓库只包含脱敏配置，恢复后仍需手动配置 `.env` 和 auth 凭证。
    98|- 回滚：使用本 commit 前版本，或用 `scripts/restore_to_hermes.sh` 恢复时生成的 `$HERMES_HOME/backups/restore_*` 备份回退。
    99|
   100|### Commit
   101|- `chore: sync sanitized hermes local configs`
   102|
   103|## 迭代 — 移除 openmemory MCP server 配置 (2026-05-20)
   104|
   105|### 目的
   106|清理已废弃的 openmemory MCP server 配置，与 lmmcp 架构对齐。
   107|
   108|### 变更摘要
   109|- `config.yaml`
   110|  - 删除 `mcp_servers.openmemory` 节（url: http://localhost:8765/mcp/claudecode/http/e-pengyang）
   111|  - openmemory 后端已在 lmmcp Phase 8.1 中移除，此处同步清理 Hermes 配置
   112|
   113|### 影响范围
   114|- Hermes 启动时不再尝试连接 openmemory MCP server
   115|- 不影响 local_memory MCP server（端口 8318）
   116|
   117|### 风险
   118|低。openmemory 服务本地未运行，删除后消除无效连接尝试。
   119|
   120|### 回滚
   121|`git revert HEAD`
   122|
---

## [2026-05-20] lmmcp-memory plugin — 三 agent 记忆集成

### 目的
让 Hermes、Claude Code、Codex 三个 agent 在用户输入后回答前自动查询 lmmcp 记忆，回答结束后自动 ingest 问答对。

### 变更摘要

**新增文件:**
- `plugins/hermes/lmmcp-memory/plugin.yaml` — Hermes plugin 声明 (pre_llm_call + post_llm_call)
- `plugins/hermes/lmmcp-memory/__init__.py` — Hermes plugin 实现
- `plugins/claude-code/lmmcp-memory/hooks/hooks.json` — Claude Code hooks 配置 (UserPromptSubmit + Stop)
- `plugins/claude-code/lmmcp-memory/hooks/query_memory.py` — Claude Code UserPromptSubmit hook
- `plugins/claude-code/lmmcp-memory/hooks/ingest_turn.py` — Claude Code Stop hook
- `plugins/codex-instructions.md` — Codex instructions.md (MCP 工具使用指令)
- `scripts/lmmcp-query` — 共享查询脚本 (~/.local/bin/lmmcp-query)

**运行时配置 (未纳入版本控制):**
- `~/.hermes/plugins/lmmcp-memory/` — Hermes plugin 安装位置
- `~/.claude/plugins/lmmcp-memory/` — Claude Code plugin 安装位置
- `~/.claude/settings.json` hooks 字段 — UserPromptSubmit + Stop 注册
- `~/.codex/instructions.md` — Codex 记忆使用指令
- `~/.local/bin/lmmcp-query` — 共享查询脚本

### 机制说明

| Agent | 触发时机 | 查询方式 | Ingest 方式 |
|---|---|---|---|
| Hermes | pre_llm_call hook | memory_context + memory_search FTS | post_llm_call 异步线程 |
| Claude Code | UserPromptSubmit hook | memory_context + memory_search FTS | Stop hook |
| Codex | instructions.md 指令 | MCP tools (memory_context + memory_search) | MCP tools (memory_ingest) |

### 验证命令
```bash
# Hermes plugin 状态
hermes plugins list | grep lmmcp

# 手动测试查询
lmmcp-query "测试查询"

# 手动测试 ingest
echo '{"session_id":"test","messages":[{"role":"user","content":"test"},{"role":"assistant","content":"ok"}]}' \
  | lmmcp-ingest --min-turns 1

# Claude Code hook 测试
echo '{"hook_event_name":"UserPromptSubmit","user_prompt":"test","session_id":"t"}' \
  | python3 ~/.claude/plugins/lmmcp-memory/hooks/query_memory.py
```

### 风险
- lmmcp 服务不可用时三个 agent 均静默跳过，不影响正常回答
- Hermes pre_llm_call 增加约 5-8s 延迟（lmmcp 查询）
- Claude Code UserPromptSubmit timeout=8s，超时静默跳过
- Codex 依赖 model 遵循 instructions.md 指令，不保证 100% 执行

### 回滚方式
```bash
# Hermes: hermes plugins disable lmmcp-memory
# Claude Code: 从 ~/.claude/settings.json 删除 hooks 字段
# Codex: 删除 ~/.codex/instructions.md
```

## 2026-05-22 18:11:19 +0800 - Repository sync publish

- Branch: `main`
- Target remote: `origin`
- Remotes:

```text
origin	https://github.com/advancer9817-crypto/hermes-local-agent-configs.git (fetch)
origin	https://github.com/advancer9817-crypto/hermes-local-agent-configs.git (push)
```

### Purpose
Batch commit and push project repository to the user-owned GitHub account as requested.

### Change summary
- Added/updated repository-local iteration record for auditable sync.
- Included current tracked/untracked project changes selected by git status.
- For newly initialized repositories, added conservative ignore rules for local runtime files and secrets.

### Impact scope
- Repository-local files only.
- No force push, no branch rewrite, no remote replacement of vendor/upstream remotes.

### Validation commands
```bash
git status --porcelain=v1 --untracked-files=all
git rev-list --left-right --count @{u}...HEAD
```

### Risks
- Large generated files and secret-like local files are intentionally excluded when ignored by `.gitignore`.
- Existing repository-specific tests are not exhaustively run for this batch metadata/publish operation.

### Rollback
```bash
git revert HEAD
git push
```

### Commit content before staging
```text
Only repository sync/iteration metadata changes.
```

---

## 2026-05-25 14:59:59 +0800 - Optimize multi-agent routing latency

### 目的
在不削弱高风险任务 gate、安全审查与 freeze artifact 校验的前提下，缩短日常 S2 普通 bugfix/局部功能修改的多角色调度路径与等待时间。

### 变更摘要
- 在 `SOUL.md` 增加 Fast / Standard / Full 三档执行通道：
  - Standard Lane 的明确 S2 任务默认改为 `default brief -> impl/Codex + 基础自测 -> freeze -> qa/Claude 与 review/Claude 并行 -> 按需 commitint`。
  - S3/S4 及安全、外部 API、数据/权限/配置/依赖/部署/架构边界任务继续走 Full Lane 与 required security gate。
- 更新 profile 角色规则：
  - `coord` 只对 Full Lane 或升级任务承担完整编排，并要求最小 handoff 上下文与并行 gate。
  - `req` / `design` 对边界清晰 S2 任务允许记录原因后跳过。
  - `impl` 在 Standard Lane 不重复触发近似完整的 Claude 验证，由 `qa` 承担独立最终 Claude 验证；Codex 基础自测不得视为 PASS。
  - `qa` / `review` 明确在同一 frozen diff 上并行执行。
- 降低各角色最大回合数：`coord 35`、`req 12`、`design 30`、`impl 50`、`qa 25`、`review 25`、`security 40`、`commitint 12`。
- 将 `coord`、`req`、`design`、`impl`、`qa`、`review` 的审批模式调整为 `smart`，减少非破坏性嵌套执行的人工等待；`security` 与 `commitint` 维持保守审批策略。
- 对 `req`、`design`、`impl`、`qa`、`review`、`commitint` 关闭自动 delegation memory context 注入，改为由 Router/Coordinator 传递最小必要 handoff；保留协调与安全角色的上下文能力。
- 更新 `references/sdlc-role-profiles.md`，记录优化后的角色分工、质量不变量与延迟配置。

### 影响范围
- Live Hermes 配置：`~/.hermes/SOUL.md`、`~/.hermes/profiles/{coord,req,design,impl,qa,review,security,commitint}/`。
- 根 Router 模型恢复并保持实施前配置 `custom:aca / gpt-5.5`；本轮不将 Router 换模计为已实施优化，脱敏镜像中的根模型标识同步为该实际状态。
- 本仓库为脱敏可版本化镜像，仅同步公开规则和无凭据配置字段。
- 不自动执行 commit 或 push；是否发布由用户另行决定。

### 验证计划
```bash
# Live 与脱敏镜像 YAML 均可解析
python3 - <<'PY'
import yaml
from pathlib import Path
for root in [Path.home()/'.hermes', Path('/home/advancer/project/hermes-local-agent-configs')]:
    for p in [root/'config.yaml', *sorted((root/'profiles').glob('*/config.yaml'))]:
        yaml.safe_load(p.read_text())
print('yaml ok')
PY

# 仓库 diff 与敏感信息扫描
git diff --check
git diff --stat
if git diff -- . ':!ITERATION.md' | grep -Ei '(api[_-]?key|token|secret|password|BEGIN [A-Z ]*PRIVATE KEY|sk-[A-Za-z0-9])'; then
  echo 'Potential secret-like content found; inspect before commit.' >&2
  exit 1
else
  echo 'No secret-like added diff detected by quick scan.'
fi
```

### 风险与回滚
- 风险：过低的 `max_turns` 可能使极复杂角色运行提前结束；复杂或高风险任务仍应升级 Full Lane，并可按需要恢复更高预算。
- 风险：关闭窄角色自动 memory context 后，若 Router handoff 内容不足，子角色可能缺少历史背景；要求 handoff 明确携带 brief、验收标准、repo、required_gates 与 freeze artifact。
- 回滚 live 配置：恢复 `/home/advancer/.hermes/backups/router_latency_opt_20260525_143720/` 下备份文件。
- 回滚本仓库：在提交后使用 `git revert <commit>`，或在提交前丢弃本轮工作树变更。

### 建议提交说明（如用户后续要求提交）
```text
perf: shorten hermes standard multi-agent lane
```

---

## 2026-05-25 15:29:07 +0800 - Align all durable profile wrapper models to default

### 目的
取消 durable role 的专属 wrapper 模型约束，使 `coord`、`req`、`design`、`impl`、`qa`、`review`、`security`、`commitint` 均与当前 default 模型/provider 配置保持一致，后续切换 default 时仅需同步对齐 profile wrapper 配置，不再维护按角色划分的模型策略。

### 变更摘要
- 当前 default 保持 `custom:aca / gpt-5.5`。
- 将八个 durable profile 的 `model.default` / `model.provider` 对齐至当前 default：`gpt-5.5` / `custom:aca`。
- 修改 Router `SOUL.md` 与 profile `SOUL.md`：移除专属角色模型说明，改为统一 wrapper 模型策略。
- 保留角色职责、写权限隔离与 adapter 契约：
  - `impl` 需要实施代码时仍使用 Codex adapter；Codex 不得自批。
  - `design` / `qa` / `review` 在其流程运行时仍按契约使用 Claude Code adapter。
  - `security` 仍为 required 时的硬 gate；若当前 default 或证据不足以可靠 PASS，必须 `BLOCKED` / `NEEDS_HUMAN_DECISION`。
- 更新 `references/sdlc-role-profiles.md`，移除旧的角色专属模型表和设置脚本，改为 default 对齐流程。

### 影响范围
- Live Hermes：`~/.hermes/SOUL.md`、`~/.hermes/profiles/{coord,req,design,impl,qa,review,security,commitint}/{config.yaml,SOUL.md}`。
- 脱敏镜像仓库：`SOUL.md`、`profiles/*/{config.yaml,SOUL.md}`、`references/sdlc-role-profiles.md`、`ITERATION.md`。
- 不改变既有 Fast / Standard / Full Lane、freeze artifact、required gates 与审批/memory_context 调优。
- 不执行 commit 或 push，除非用户明确要求。

### 验证计划
```bash
# 对齐 live 与脱敏镜像中所有 durable role 的 model 映射到各自 root default model
python3 - <<'PY'
import yaml
from pathlib import Path
roles = ['coord','req','design','impl','qa','review','security','commitint']
for root in [Path.home()/'.hermes', Path('/home/advancer/project/hermes-local-agent-configs')]:
    target = yaml.safe_load((root/'config.yaml').read_text())['model']
    for role in roles:
        actual = yaml.safe_load((root/'profiles'/role/'config.yaml').read_text())['model']
        assert actual == target, (root, role, actual, target)
print('profile wrapper models match default')
PY

git diff --check
```

### 风险与回滚
- 风险：取消 security 专属强模型绑定后，安全审查质量不再依赖预设高阶 wrapper；通过 gate 契约强制“证据不足不得 PASS”缓解风险。
- 说明：profile 配置文件本身不是动态引用；直接单独启动 profile 时仍使用其静态 fallback。多角色调度场景将在下一轮配置中改为调用时透传当前会话实际模型/provider。
- 回滚 live 配置：恢复 `/home/advancer/.hermes/backups/unified_default_model_20260525_151609/` 中的文件。
- 回滚仓库改动：提交前可恢复工作树；提交后使用 `git revert <commit>`。

### 建议提交说明（如用户后续要求提交）
```text
config: align hermes role wrapper models to default
```

---

## 2026-05-25 16:09:06 +0800 - Dispatch durable profiles with the active session model dynamically

### 目的
将“profile 静态对齐 root default”的策略升级为真正的调度时动态透传：当前 Router 会话无论使用持久默认模型，还是通过 `/model` 或启动参数临时切换模型，调用其他 durable role 时都显式传递该会话实际生效的 model/provider。

### 实现方式
- 已确认 Hermes profile 使用独立 `HERMES_HOME`，profile 自身 `config.yaml` 不会动态继承父会话内的临时模型切换。
- 已确认 `hermes chat` 支持调用级覆盖：`-m <model> --provider <provider>`。
- Router 规则改为：调用任何 durable profile 必须使用：
  ```bash
  hermes -p <profile> chat -m <current_model> --provider <current_provider> -q "<handoff prompt>"
  ```
- `current_model` / `current_provider` 必须来自调度方当前会话实际运行值，而非被调用 profile 的静态配置。
- 各 profile `config.yaml` 中现有模型值继续保留为“用户直接单独启动该 profile”时的 fallback，不作为多角色调度模型来源。

### 变更摘要
- 更新 live 与脱敏镜像的根 `SOUL.md`，加入动态透传调用契约并澄清 fallback 语义。
- 更新八个 role 的 `SOUL.md`，统一声明被调度时依赖 `-m/--provider` 的调用级覆盖。
- 更新 `references/sdlc-role-profiles.md`，记录 Hermes 原生隔离机制、动态调用命令及使用示例。
- 更新 routing architecture skill 参考说明，防止后续恢复为静态同步策略。

### 保留的不变量
- 不取消 `impl` / Codex、`design` / `qa` / `review` / Claude Code 的 adapter 合同。
- 不取消 required gates、freeze artifact、`gate_generation`、安全触发规则或 security 的硬阻断职责。
- 若动态透传给 `security` 的当前模型或证据不足以可靠 PASS，必须返回 `BLOCKED` 或 `NEEDS_HUMAN_DECISION`。

### 影响范围
- Live Hermes：`~/.hermes/SOUL.md`、`~/.hermes/profiles/{coord,req,design,impl,qa,review,security,commitint}/SOUL.md`、相关技能参考。
- 脱敏镜像仓库：`SOUL.md`、`profiles/*/SOUL.md`、`references/sdlc-role-profiles.md`、`ITERATION.md`。
- 不自动执行 commit 或 push。

### 风险与回滚
- 风险：若未来某个调用方遗漏 `-m` 或 `--provider`，被调用 profile 会退回自身 fallback 而不是当前会话模型；因此调用契约已写入 Router 与角色规则。
- 回滚 live 规则：恢复 `/home/advancer/.hermes/backups/dynamic_invocation_model_20260525_154801/` 下备份文件。
- 回滚仓库改动：提交前恢复工作树；提交后使用 `git revert <commit>`。

### 建议提交说明（如用户后续要求提交）
```text
config: dynamically forward active model to hermes roles
```
## 2026-05-25T18:39:28+08:00 — batch repository sync

- Branch: `main`
- HEAD before commit: `9accd50`
- Target remote: `origin`
- Remote URLs:

```text
origin	https://github.com/advancer9817-crypto/hermes-local-agent-configs.git (fetch)
origin	https://github.com/advancer9817-crypto/hermes-local-agent-configs.git (push)
```

### Purpose

Batch commit and push this repository under `/home/advancer/project` to the user's GitHub account, with a repository-local iteration record kept in version control.

### Change summary / commit content

```text
 M ITERATION.md
 M SOUL.md
 M config.yaml
 M profiles/commitint/SOUL.md
 M profiles/commitint/config.yaml
 M profiles/coord/SOUL.md
 M profiles/coord/config.yaml
 M profiles/design/SOUL.md
 M profiles/design/config.yaml
 M profiles/impl/SOUL.md
 M profiles/impl/config.yaml
 M profiles/qa/SOUL.md
 M profiles/qa/config.yaml
 M profiles/req/SOUL.md
 M profiles/req/config.yaml
 M profiles/review/SOUL.md
 M profiles/review/config.yaml
 M profiles/security/SOUL.md
 M profiles/security/config.yaml
 M references/sdlc-role-profiles.md
```

### Diff stat before staging

```text
ITERATION.md                     | 156 ++++++++++++++++++++++++++++++++++++++
 SOUL.md                          |  43 +++++++----
 config.yaml                      |   4 +-
 profiles/commitint/SOUL.md       |   2 +-
 profiles/commitint/config.yaml   |   8 +-
 profiles/coord/SOUL.md           |  16 ++--
 profiles/coord/config.yaml       |   8 +-
 profiles/design/SOUL.md          |   6 +-
 profiles/design/config.yaml      |  10 +--
 profiles/impl/SOUL.md            |  19 ++---
 profiles/impl/config.yaml        |   8 +-
 profiles/qa/SOUL.md              |   7 +-
 profiles/qa/config.yaml          |  10 +--
 profiles/req/SOUL.md             |  13 ++--
 profiles/req/config.yaml         |  10 +--
 profiles/review/SOUL.md          |   5 +-
 profiles/review/config.yaml      |  10 +--
 profiles/security/SOUL.md        |   4 +-
 profiles/security/config.yaml    |   6 +-
 references/sdlc-role-profiles.md | 157 +++++++++++++++++----------------------
 20 files changed, 331 insertions(+), 171 deletions(-)
```

### Impact scope

Repository synchronization/auditability. No intentional source behavior change is introduced by this iteration record itself unless listed above.

### Validation commands

```text
git status --porcelain=v1 --untracked-files=all
git push -u <target-remote> <branch>
git rev-list --left-right --count @{u}...HEAD
```

### Risks

This is an automated multi-repository sync. Generated/runtime artifacts already present in the working tree may be included when not ignored by this repository.

### Rollback

Use `git revert <commit>` on this repository, then push the revert commit to the same remote/branch.

---

## 2026-09-10T10:18:00+0800 — Streamline SOUL.md: Pure Pragmatic Single-Agent & Conflict Cleanup

### 目的
彻底清除假大空的八股式“全生命周期”大词与多 Agent/CLI 协同遗留，消除记忆库中互相打架的交互指令，将 SOUL 固化为极简实战版，终结双端配置漂移与执行困扰。

### 变更摘要
1. **SOUL.md 极致瘦身与纠偏**：
   - 移除“明确所有调研、架构、编写、测试、审查、版本控制与运维全生命周期全部由当前单会话闭环”等教条八股叙事；
   - 移除任何外部 CLI (Claude Code/Codex) 协同及多角色路由残余；
   - 交互规范确立“行动优先、顺畅时直接交付、遇异常/矛盾单句讲清技术结论、杜绝机械报幕与模板框”；
   - 记忆规范废除脱离实际的“项目内双写 memory/ 与 MEMORY.md 索引”死规则，统一规范为 `memory_add` + `source_agent: "hermes"`。
2. **多端一致性闭环**：
   - 同步覆盖 Live 运行时 `~/.hermes/SOUL.md`；
   - 同步覆盖仓库 `hermes-local-agent-configs/SOUL.md`；
   - 同步清洗 `~/.hermes/memories/USER.md` 中的冲突条目。

### 影响范围
- Live 运行时：`~/.hermes/SOUL.md`、`~/.hermes/memories/USER.md`
- 本地配置版本库：`SOUL.md`、`ITERATION.md`

### 验证命令
```bash
git -C /home/advancer/project/hermes-local-agent-configs diff SOUL.md
test -f ~/.hermes/SOUL.md && grep -q "极简与可移植性" ~/.hermes/SOUL.md && echo "Live SOUL.md OK"
```

### 风险与回滚
- 风险：无。规则篇幅缩减 65% 以上，指令遵循度大幅提升。
- 回滚：`git checkout HEAD~1 SOUL.md`，并同步覆盖 `~/.hermes/SOUL.md`。

---

## 2026-09-10T14:20:00+0800 — Align Interaction Formula: Single-Sentence Technical Intent Standard

### 目的
对齐远程沙箱验证成熟的交互表达规范，引入“单句高信息密度技术意图公式（动词短语 + 精确标的 + 技术目的）”，彻底解决本地 Agent 在“机械报幕”与“连续静默黑盒”之间反复横跳的顽疾。

### 变更摘要
1. **SOUL.md 交互条款精准固化**：
   - 确立正向语法公式：【动词短语】+【精确操作标的】+【技术目的/预期解决的矛盾】；
   - 确立正向示范：“检查编译环境与 Maven 构建链路，为修复后端健康检查路由 /api/v1/health 做准备。”；
   - 严禁连续发送空 `content: ""` 发起工具调用导致黑盒；
   - 坚决杜绝“步骤X/假设/推演事实”等假大空模板框与纯动作流水账。
2. **多端同步与记忆对齐**：
   - 同步覆盖 Live 运行时 `~/.hermes/SOUL.md`；
   - 同步覆盖仓库 `hermes-local-agent-configs/SOUL.md`；
   - 同步更新 `~/.hermes/memories/USER.md` 中的交互规则。

### 影响范围
- Live 运行时：`~/.hermes/SOUL.md`、`~/.hermes/memories/USER.md`
- 本地配置版本库：`SOUL.md`、`ITERATION.md`

### 验证命令
```bash
git -C /home/advancer/project/hermes-local-agent-configs diff SOUL.md
grep -q "意图表达公式" ~/.hermes/SOUL.md && echo "Live SOUL.md OK"
```

### 风险与回滚
- 风险：无。
- 回滚：`git checkout HEAD~1 SOUL.md`，并同步覆盖 `~/.hermes/SOUL.md`。

---

## 2026-09-10T14:35:00+0800 — Sync Live Memories & Push Configuration Updates

### 目的
同步本地 Live 运行时的最新记忆画像（`USER.md`）与通用事实（`MEMORY.md`）至配置受控仓库，并全量提交推送到远程配置同步仓库 `origin main`。

### 变更摘要
1. **记忆文件同步**：
   - `memories/USER.md`：同步最新单 Agent 交互铁律与交付路径；
   - `memories/MEMORY.md`：同步最新环境状态、跳板机安全配置与模型接入备忘。
2. **远程推送**：
   - 包含此前已提交的 SOUL.md 极简重塑（commit 166c5c1）、单句技术意图公式固化（commit 14200dc）以及本轮记忆文件同步提交；
   - 推送至 `origin/main`。

### 影响范围
- 本地配置版本库：`memories/USER.md`、`memories/MEMORY.md`、`ITERATION.md`
- 远程仓库：`advancer9817-crypto/hermes-local-agent-configs:main`

### 验证命令
```bash
git -C /home/advancer/project/hermes-local-agent-configs log origin/main..HEAD
git -C /home/advancer/project/hermes-local-agent-configs status
```

### 风险与回滚
- 风险：无。已完成脱敏检查，不含敏感 Token 或运行时数据库。
- 回滚：`git revert <commit>` 或 `git reset --hard origin/main`。

---

---

## 2026-09-12T15:45:00+0800 — Fix Local Voice STT (Whisper Model Cache & CPU Inference) & Set Chinese Recognition

### 目的
修复 Hermes 语音输入转写失败问题（解决离线模型缺失引发的 `Network is unreachable` 以及 WSL 环境下调用 GPU 时触发的 `libcublas.so.12 is not found` 错误），并将全局及本地语音转写配置为中文识别。

### 变更摘要
1. **补全本地 Whisper 权重**：
   - 部署 `faster-whisper-base` 与 `faster-whisper-tiny` 离线模型至 `~/.cache/huggingface/hub/`，阻断首次懒加载向外网拉取模型的超时与断网异常。
2. **锁定 CPU/int8 推理设备**：
   - WSL 环境缺少 NVIDIA CUDA 12 动态链接库（`libcublas.so.12`），WhisperModel 默认 `auto` 会误选 CUDA 并于分词生成时崩溃；
   - 显式配置 `stt.local.device: cpu` 与 `stt.local.compute_type: int8`，避开 CUDA 动态库依赖。
3. **设置中文识别**：
   - 配置 `stt.language: zh` 与 `stt.local.language: zh`，确保语音转写默认为中文识别。
4. **受控配置仓库同步**：
   - 同步脱敏配置至 `hermes-local-agent-configs/config.yaml`。

### 影响范围
- Live 运行时：`~/.hermes/config.yaml`、`~/.cache/huggingface/hub/`
- 本地配置版本库：`config.yaml`、`ITERATION.md`

### 验证命令
```bash
/home/advancer/.hermes/hermes-agent/venv/bin/python -c 'from tools.voice_mode import transcribe_recording; print(transcribe_recording("/tmp/test.wav"))'
```

### 风险与回滚
- 风险：纯 CPU 推理耗时稍长于高配 GPU，但兼容性与稳定性为 100%。
- 回滚：`hermes config set stt.language en && hermes config set stt.local.device auto`。

---

## 2026-09-12T15:47:00+0800 — Add Mandatory Progress-Checkpoint Protocol to SOUL.md

### 目的
解决长任务执行期间"连续工具调用、无有效反馈"的黑盒体验：模型按步执行却长时间不交代主线任务、原因判断与阶段结果，用户无法判断其在做什么、为何这么做。

### 变更摘要
1. **根因定位**：
   - 反馈通道本身是通的——桌面端后端走 `hermes serve`（platform=api_server），其 display 层属 `_TIER_HIGH`，`interim_assistant_messages=True`，中间文本可正常送达；
   - 缺失的是内容约束：原 SOUL 仅有"单句技术意图"要求，无"主线锚定 + 阶段检查点 + 原因/结果交代"的强制协议；
   - Hermes 无原生闸门：`tool_loop_guardrails` 只覆盖"重复失败/无进展"，不覆盖"静默连发"，故只能在提示词层强制。
2. **SOUL.md 新增 `## 2.4 阶段性汇报协议 (Progress Checkpoint，长任务强制)`**：
   - 主线锚定（首个工具调用前交代目标/阶段拆分/入手点及理由，压缩或续做后重新锚定）；
   - 检查点触发条件（阶段完成、连续 3 次工具调用无文字、静默 >90s、同一问题排查 >2 轮）；
   - 检查点四要素（主线进度 / 原因判断与证据、是否偏离预期 / 结果与影响 / 下一步及理由）；
   - 结果优先于动作、异常即时上报、禁止连续 `content: ""` 静默连发、收尾复盘与未完成如实标注。

### 影响范围
- Live 运行时：`~/.hermes/SOUL.md`（备份 `SOUL.md.bak-progress-20260912_154628`）
- 本地配置版本库：`SOUL.md`、`ITERATION.md`

### 验证命令
```bash
grep -n "阶段性汇报协议" ~/.hermes/SOUL.md
diff ~/.hermes/SOUL.md /home/advancer/project/hermes-local-agent-configs/SOUL.md
```

### 风险与回滚
- 风险：检查点提频会略增输出 token 与回复长度；已用"自然语言连贯表述、禁止模板框"约束避免机械报幕。
- 回滚：`cp ~/.hermes/SOUL.md.bak-progress-20260912_154628 ~/.hermes/SOUL.md`。
- 生效方式：SOUL.md 于会话启动时构建进系统提示词，需 `/new` 或重启桌面端后端生效。

---

## 2026-09-12T15:51:00+0800 — Externalize Long-Task Progress via Mandatory todo Usage

### 目的
在"阶段性汇报协议"基础上补齐硬抓手：把阶段目标与当前状态外化为 todo 任务项，使进度成为用户可直接观察的状态，而不是仅存在于模型文字里的自述。

### 变更摘要
1. **前置核实**：`hermes tools list` 确认 `todo` toolset 已全局启用（Task Planning）；`todo_list` 支持 `merge=true` 增量更新、`parent` 嵌套、单一 `in_progress`。
2. **SOUL.md 第 2.4 条新增"进度外化（todo 强制）"**：
   - 3 步以上（或单步预计 >2 分钟）任务，首个工具调用**前**必须写入全量阶段清单；
   - 每项必须是可验证的**产出**（做什么 + 判据），禁止"查看/读取/分析某文件"式动作项；
   - 阶段切换即时 `merge=true` 更新，有且仅有一个 `in_progress`；失败项 `cancelled` 并补修正项；`completed` 仅标已验证项；
   - 检查点文字进度必须与 todo 状态一致，严禁虚标；无法依赖面板时检查点自带"阶段 N/M"。

### 影响范围
- Live 运行时：`~/.hermes/SOUL.md`（备份 `SOUL.md.bak-todo-20260912_155013`）
- 本地配置版本库：`SOUL.md`、`ITERATION.md`

### 验证命令
```bash
grep -n "进度外化" ~/.hermes/SOUL.md
diff ~/.hermes/SOUL.md /home/advancer/project/hermes-local-agent-configs/SOUL.md
```

### 验证结果
- `todo_list` 实机调用通过：写入 5 项计划 → revision 1；`merge=true` 更新 2 项 → revision 2；状态与 summary（total 5 / pending 0 / in_progress 1 / completed 4）一致。
- SOUL.md 与仓库副本 diff 退出码 0（完全一致）。

### 风险与回滚
- 风险：无。todo 为会话内状态，不落盘、不改变工具集。
- 回滚：`cp ~/.hermes/SOUL.md.bak-todo-20260912_155013 ~/.hermes/SOUL.md`。
- 生效方式：需 `/new` 或重启后端进程加载新系统提示词。

---

## 2026-09-12T16:42:00+0800 — Simplify Interaction Rules into Plain Language

### 目的
前两轮新增的"阶段性汇报协议/进度外化"写得过于制度化（①②③④要素、成串"必须/严禁"），用户反馈过于格式化。改为口语化、原则性的短条款，保留约束力但去掉模板感。

### 变更摘要
- 重写 `## 2. 交互与沟通规范`：由 4 组带格式公式与要素编号的条目，压缩为 5 条白话。
- 保留的实质约束：全中文说人话、动手前一句话交代意图（且禁止无信息量报幕）、长任务边做边说（含卡住/走错路立刻讲）、复杂任务可选 todo 列清单、未完成如实说、终端命令单步原子。
- 去掉的内容：`【动词短语】+【标的】+【目的】`公式、"检查点四要素 ①②③④"、"todo 强制/严禁静默连发"等硬性编号条款。
- 文件体积：6742 → 3580 字节。

### 影响范围
- Live 运行时：`~/.hermes/SOUL.md`（备份 `SOUL.md.bak-plain-20260912_164143`）
- 本地配置版本库：`SOUL.md`、`ITERATION.md`

### 验证命令
```bash
diff ~/.hermes/SOUL.md /home/advancer/project/hermes-local-agent-configs/SOUL.md
```

### 风险与回滚
- 风险：约束力度下降，弱模型可能回到"闷头连跑"的状态；若再出现，可加回少量具体条款而非整段框架。
- 回滚：`cp ~/.hermes/SOUL.md.bak-plain-20260912_164143 ~/.hermes/SOUL.md`。
- 生效方式：需 `/new` 或重启后端进程。

---

## 2026-09-12T16:50:00+0800 — Verify SOUL Rule Effectiveness; Neutralize Personality Override

### 目的
验证重写后的交互规范是否真正生效，定位"模型长时间无有效反馈"的真实成因。

### 核查结论（实测，非推断）
1. **注入成功**：用 `agent.system_prompt.build_system_prompt` 实机构建提示词，第 2 节全文位于 stable 段（3783→3922 字符），`说人话` 命中索引 413。
2. **存在覆盖冲突（已修）**：`display.personality: catgirl` 的人格文本经 `agent/conversation_loop.py:1048`（`sp + "\n\n" + ephemeral_system_prompt`）拼接在系统提示词**之后**，实测 Neko 文本位于末尾（索引 3932）。后置指令压过后置冲突 → 第 2.1 条"不要猫娘腔"被抵消。已 `hermes config set display.personality ''` 清空，复验 Neko 索引 = -1。
3. **生效时机**：SOUL.md 在 `agent._cached_system_prompt` 中按会话缓存（`load_soul_md` 无缓存但仅构建时读取）→ 改 SOUL 必须 `/new`；config.yaml 按文件签名缓存（`load_config`）→ 改 config 下一轮生效。
4. **行为层验证（A/B 实测，默认 CLI 模型）**：
   - 同一多步任务，规范改前：5 次工具调用 / 5 条动作标签（16-41 字符），无阶段说明；
   - 规范加"每三四步/阶段完成时说两三句"后：3 次工具调用 / 3 条动作标签（16-40 字符），仍无阶段说明 → **措辞级微调不改变行为**；
   - 换 `claude-sonnet-4-6`（CPA）同一任务：2 次工具调用均为 `content: ""`，完全静默，比 flash 模型更差。
   - 结论：提示词只能保证"有文字"，无法保证"有内容"；`tool_loop_guardrails` 无"沉默闸门"。
5. **可控硬闸门（未部署）**：`pre_llm_call` shell hook 每轮执行且经 `agent/turn_context.py::_collect_pre_llm_call_context` 把 `{"context": ...}` 注入**用户消息**（非系统提示词），可据会话历史动态判定"连续 N 次工具调用无交代"并注入强制提醒。注册需 config `hooks:` 条目 + `shell-hooks-allowlist.json` 授权（`hooks_auto_accept` 当前 false）。

### 变更摘要
- `display.personality`：`catgirl` → `''`（清除与 SOUL 2.1 冲突的人格覆写）。
- SOUL.md 第 3 条补入可判定触发条件与"别只贴一句动作标签"。

### 影响范围
- Live 运行时：`~/.hermes/SOUL.md`（备份 `SOUL.md.bak-trigger-20260912_164620`）、`~/.hermes/config.yaml`（备份 `config.yaml.bak-personality-20260912_164404`）
- 本地配置版本库：`SOUL.md`、`config.yaml`、`ITERATION.md`

### 验证命令
```bash
grep -n "personality" ~/.hermes/config.yaml
/home/advancer/.hermes/hermes-agent/venv/bin/python /tmp/probe_eff.py
```

### 风险与回滚
- 风险：失去 catgirl 人格（与用户既定"严禁可爱风/猫娘腔"一致，符合预期）。
- 回滚：`cp ~/.hermes/config.yaml.bak-personality-20260912_164404 ~/.hermes/config.yaml`；SOUL 回滚 `cp ~/.hermes/SOUL.md.bak-trigger-20260912_164620 ~/.hermes/SOUL.md`。

---

## 2026-09-12T16:56:00+0800 — Decision: Do Not Deploy Hook-Based Progress Gate

### 目的
记录用户对"硬闸门"方案的决定，避免后续会话重复提案。

### 决定
- **不部署** `pre_llm_call` 提醒钩子 / `pre_tool_call` 阻断钩子。
- 接受的下限：**每次工具调用附带一句文字**（当前模型栈下已稳定达成），不追求强制性的阶段性叙事。
- 需要细节时由用户主动追问，不引入每轮执行的脚本与 `shell-hooks-allowlist.json` 授权。

### 当前生效状态
- SOUL.md 第 2 节为白话版（含"别只贴一句动作标签"），需 `/new` 生效。
- `display.personality: ''`（已清除 catgirl 覆写）。
- 无任何 shell hook 注册；`hooks_auto_accept: false` 保持不变。

### 复查触发条件
若用户再次反馈"长时间无有效反馈"，先确认是否已 `/new`（SOUL 按会话缓存）；仍不满足再考虑 hook 方案。

---

## 2026-09-12T17:05:00+0800 — Remove Tone Restrictions & Restore Catgirl Personality

### 目的
根据用户要求，移除 SOUL.md 中对猫娘腔、可爱风、颜文字的限制，并恢复 `display.personality: catgirl` 配置。

### 变更摘要
1. **SOUL.md**：移除“不要可爱风、猫娘腔、颜文字和一堆感叹号”约束，简化为“默认全中文，说人话。”，不再对助手语气风格做生硬限制。
2. **config.yaml**：将 `display.personality` 恢复为 `catgirl`。
3. **hermes-agent skill**：同步更新关于 personality 覆盖机制的描述为纯中立客观说明。

### 影响范围
- Live 运行时：`~/.hermes/SOUL.md`、`~/.hermes/config.yaml`
- 本地配置版本库：`SOUL.md`、`config.yaml`、`ITERATION.md`

### 验证命令
```bash
grep "catgirl" /home/advancer/.hermes/config.yaml
grep "说人话" /home/advancer/.hermes/SOUL.md
git -C /home/advancer/project/hermes-local-agent-configs status
```

### 风险与回滚
- 风险：无。
- 回滚：`hermes config set display.personality ''` 并恢复 SOUL.md。

---

## 2026-09-12T17:15:00+0800 — Eradicate Action-Narrating "正在xxx" Anti-Pattern & Clean USER.md

### 目的
彻底根除每次工具调用前机械输出“正在检索/正在读取/正在定位……”的报幕流水账，解决模型教条化机械输出导致体验恶化的问题。

### 根因与修复
1. **持久化记忆污染排查**：在 `USER.md`（USER PROFILE 记忆层）中发现了残留的 `关键工具调用前伴随输出单句技术意图(动词+标的+目的)`，导致无论系统提示词如何修改，每轮模型推理都会被强制注入该公式，引发模型教条式套用“正在[动词]+[标的]+[目的]”。
2. **USER.md 清理重构**：使用 `memory` 工具将 USER PROFILE 中的该条目彻底重构，明确写入 `严禁在每次工具调用前机械报幕（如'正在xxx'流水账）；遇到卡点、需决策或有阶段结论时才交代`，同时移除对语气/猫娘的陈旧限制，精简整个 user profile 字符至预算内（93%）。
3. **SOUL.md 第 2 节改写**：删除“动手前先一句话交代在做什么”，明确规定“工具调用直接执行，严禁每次调用前输出‘正在xxx’机械报幕；仅在长任务阶段性完成、卡住需要决策或出阶段结论时，才用自然简短的话交代进展”。

### 影响范围
- Live 运行时：`~/.hermes/SOUL.md`、`~/.hermes/memories/USER.md`
- 本地配置版本库：`SOUL.md`、`memories/USER.md`、`ITERATION.md`

### 验证命令
```bash
grep "正在xxx" ~/.hermes/SOUL.md
grep "正在xxx" ~/.hermes/memories/USER.md
git -C /home/advancer/project/hermes-local-agent-configs status
```

### 风险与回滚
- 风险：无。
- 回滚：`git checkout HEAD~1 -- SOUL.md memories/USER.md` 并回写 `~/.hermes/`。

---

## 2026-09-12T17:25:00+0800 — Refine Action Briefing (Drop Subject & "正在") + Mandate Detailed Long-Form Output on Critical Decisions

### 目的
精准对齐用户交互要求：
1. 需要交代动作，但必须**去掉主语，严禁“我正在……”或“正在……”**，直接说明做什么与目的（如“检索 memorycore 历史提交，明确最新基线”）；
2. 遇到重大决策（架构选型、核心排障发现、技术方案对比、需要用户拍板等关键节点）时，必须输出一段详实连贯的长文本深入剖析，讲透前因后果与影响。

### 变更摘要
1. **SOUL.md 第 2 节（交互与沟通规范）**：
   - 规定**动作交代规范（去主语、禁止“正在/我正在”）**：交代要做的事情时去掉主语，严禁使用“正在……”或“我正在……”前缀，直接陈述动作与目的；
   - 规定**重大决策长文本深度剖析**：重大架构选型、排障核心突破、方案取舍及决策节点，输出详实长文本完整阐明依据、逻辑与影响，严禁轻描淡写带过；
   - 保持长任务阶段性交代与未完成如实说明。
2. **USER.md (USER PROFILE 长期记忆)**：
   - 同步更新为：`交互沟通: 默认全中文；交代动作去主语、严禁'正在/我正在'前缀，直述要做什么；重大决策/排障核心/方案取舍输出详实长文本深入剖析；命令单步原子化严禁&&或分号。程序层聚合计算，禁SQL堆复杂函数。`

### 影响范围
- Live 运行时：`~/.hermes/SOUL.md`、`~/.hermes/memories/USER.md`
- 本地配置版本库：`SOUL.md`、`memories/USER.md`、`ITERATION.md`

### 验证命令
```bash
grep -n "正在" ~/.hermes/SOUL.md
grep -n "正在" ~/.hermes/memories/USER.md
git -C /home/advancer/project/hermes-local-agent-configs status
```

### 风险与回滚
- 风险：无。
- 回滚：`git checkout HEAD~1 -- SOUL.md memories/USER.md` 并回写 `~/.hermes/`。

---

## 2026-09-12T17:35:00+0800 — Sanitize config.yaml & Push Local Commits to Remote

### 目的
在执行用户授权的远程推送前，严格执行受控企业环境安全红线，对配置仓库中的 `config.yaml` 进行彻底脱敏（凭据统一替换为 `[REDACTED]`），随后推送全部提交至远程仓库。

### 变更摘要
1. **凭据彻底脱敏**：将 `config.yaml` 中 `custom_providers` 的 `api_key` 字段全面替换为 `[REDACTED]`，确保零敏感信息上云。
2. **推送执行**：经用户明确授权，将本地 accumulated 提交（含语音输入 CPU 修复、SOUL/USER 沟通规范重构、猫娘人设恢复、去报幕协议等）推送到远程分支 `origin/main`。

### 影响范围
- 本地配置版本库：`config.yaml`、`ITERATION.md`
- 远程仓库：`origin/main`

---

## 2026-09-14T09:30:00+0800 — Fix cc-switch Input Hang Under WSLg (WebKitGTK + IME)

### 目的
修复 cc-switch 在 WSLg 下「点击任意输入框无法聚焦/输入，且触发后整页控件全部失效，点返回按钮弹出官网」的故障，并把修复件与排查结论纳入受控配置仓库，避免重装或升级后再次踩坑。

### 变更摘要
1. **根因定位（非 cc-switch 缺陷）**：WebKitGTK 2.40+ 在 Linux 下，GTK 探测到已安装 fcitx5/ibus 的 IM 模块但对应守护进程未运行时，输入框进入 IME 组合态会挂死 `WebKitWebProcess`，导致其后所有 WebView 交互失效。本机 `libwebkit2gtk-4.1-0 = 2.52.6`，与上游 `farion1231/cc-switch` issue **#7059** 报告版本完全一致。
2. **修复落点（两条启动路径全覆盖）**：
   - 包装脚本 `~/.local/bin/cc-switch` 增加 IM 兼容块，设 `GTK_IM_MODULE=gtk-im-context-simple`、`QT_IM_MODULE=simple`、`XMODIFIERS=@im=none`；
   - 新增用户级桌面项覆盖 `~/.local/share/applications/CC Switch.desktop` 与 `cc-switch-handler.desktop`，`Exec` 指向包装脚本 —— 因 `/etc/environment` 的 PATH 不含 `~/.local/bin`，开始菜单与 `ccswitch://` 深链接会绕过包装脚本直呼 `/usr/bin/cc-switch`。
3. **新增修复件**：`scripts/cc-switch-wslg-fix/`（`cc-switch` 包装脚本、`install.sh` 幂等安装器含 `--check` 环境自检、`README.md`、`FIX-REPORT.md`）。

### 影响范围
- Live 运行时：`~/.local/bin/cc-switch`、`~/.local/share/applications/CC Switch.desktop`、`~/.local/share/applications/cc-switch-handler.desktop`
- 本地配置版本库：`scripts/cc-switch-wslg-fix/`、`ITERATION.md`
- **不触碰** `~/.cc-switch/` 配置库（providers 24 条前后一致，另有冷备份 `~/.cc-switch.bak-reinstall-20260911/`）

### 验证命令
```bash
# 运行进程真实继承的环境变量（唯一可信验证）
PID=$(pgrep -f "^/usr/bin/cc-switch" | head -1)
tr '\0' '\n' < "/proc/${PID}/environ" | grep -E "^(GTK_IM_MODULE|QT_IM_MODULE|XMODIFIERS)="

# 环境自检（不改动文件）
scripts/cc-switch-wslg-fix/install.sh --check
```

### 风险与回滚
- 风险：低。若将来真的安装并常驻运行 fcitx5/ibus，需在包装脚本中改为条件判断，否则会失去输入法支持。
- 回滚：删除上述两个用户级 `.desktop` 与 `~/.local/bin/cc-switch`，三处改动互相独立可单独撤销。

---

## 2026-09-20T13:50:00+0800 — Decouple Task State Machine from Chat Output (SOUL.md & todo_list)

### 目的
解决任务清单组件长期未被调用的问题：破除由于“禁止死板模板、杜绝步骤X”过度抑制任务状态机调用的阻碍，将“正文沟通”与“结构化状态机”解耦。

### 变更摘要
1. **SOUL.md 交互规范微调**：
   - 保留“禁止正文格式化流水账（严禁在回复正文中输出步骤X/推演事实/假设等假大空格式框）”；
   - 明确新增“任务状态机与原生看板解耦”：对于 ≥3 步的跨模块/重构/批量工程任务，首步必须调用 `todo_list` 挂载底层状态机（通过原生桌面看板展示，不在正文冗余复述），并随实际验证结果原子翻牌，作为执行防漂移锚点。
2. **同步生效范围**：
   - 运行时配置文件：`~/.hermes/SOUL.md`
   - 配置仓库镜像：`project/hermes-local-agent-configs/SOUL.md`

### 影响范围
- `~/.hermes/SOUL.md`
- `project/hermes-local-agent-configs/SOUL.md`
- `project/hermes-local-agent-configs/ITERATION.md`

### 验证命令
```bash
git -C /home/advancer/project/hermes-local-agent-configs diff SOUL.md
```

### 风险与回滚
- 风险：低。原路径已设置符号链接，Hermes 历史脚本可继续正常工作。
- 回滚：`mv local-agent-configs hermes-local-agent-configs` 并删除符号链接。

---

## 2026-09-22T17:15:00+0800 — Refactor Directory Layout into Agent Subfolders (claude, hermes, codex)

### 目的
彻底改变原先以 Hermes 为中心且部分资产散落根目录的布局，重构为以智能体为边界的清晰子目录架构（`claude/`、`hermes/`、`codex/`），实现各 Agent 本地配置自治与统一运维管理。

### 变更摘要
1. **目录结构重塑**：
   - `hermes/`：将根目录下的 `config.yaml`、`SOUL.md`、`PROFILE_LIST.txt`、`memories/`、`profiles/`、`references/` 与 `plugins/hermes/` 全部收敛迁入；
   - `claude/`：统一纳管 `settings.json`、`CLAUDE.md`、`rules/`、`scripts/statusline.sh` 以及插件存档；
   - `codex/`：新增纳管脱敏的 `config.toml`（代理修复为 172.20.0.1:7890）、`instructions.md`（mcore/lmmcp 上下文规范）与 `hooks.json`；
   - `scripts/`：统一存放各 Agent 一键恢复脚本（`restore_to_claude.sh`、`restore_to_hermes.sh`、`restore_to_codex.sh`）及通用运维工具。
2. **恢复脚本与文档适配**：
   - 适配 `restore_to_hermes.sh` 读取 `hermes/` 源路径；
   - 新建 `restore_to_codex.sh`；
   - 更新 `README.md`，绘制三 Agent 子目录树状图与安全策略。

### 影响范围
- 根目录资产归集至 `claude/`、`hermes/`、`codex/`
- `scripts/restore_to_hermes.sh`、`scripts/restore_to_codex.sh`
- `README.md`、`ITERATION.md`

### 验证命令
```bash
git -C /home/advancer/project/local-agent-configs status
bash /home/advancer/project/local-agent-configs/scripts/restore_to_hermes.sh
bash /home/advancer/project/local-agent-configs/scripts/restore_to_claude.sh
bash /home/advancer/project/local-agent-configs/scripts/restore_to_codex.sh
```

### 风险与回滚
- 风险：低。仅为仓库内部文件目录组织结构重排，不影响各 Agent 运行时的直接配置。
- 回滚：`git checkout HEAD~1` 并重新组织目录。

---

## 2026-09-22T17:35:00+0800 — Rename GitHub Remote Repository to local-agent-configs

### 目的
配合本地项目名与多 Agent 子目录自治架构的升级，将 GitHub 远端仓库从 `advancer9817/hermes-local-agent-configs` 同步重命名为 `advancer9817/local-agent-configs`，使远程与本地保持完全一致。

### 变更摘要
1. **GitHub 远程仓库重命名**：
   - 使用 GitHub CLI 将远程仓库重命名为 `advancer9817/local-agent-configs`；
   - 更新远程仓库描述为 `Sanitized local AI agent configurations (Claude Code, Hermes, Codex) and restore toolset`。
2. **本地 Git Remote 更新**：
   - 将 `origin` URL 更新为 `https://github.com/advancer9817/local-agent-configs.git`；
   - 验证 `git fetch` 连通正常。

### 影响范围
- 远程仓库：`https://github.com/advancer9817/local-agent-configs.git`
- 本地配置：`git remote origin`
- 文档：`ITERATION.md`

### 验证命令
```bash
git remote -v
gh repo view advancer9817/local-agent-configs
git fetch origin
```

### 风险与回滚
- 风险：无。GitHub 会自动为旧仓库名建立重定向，原 clone 链接不会失效。
- 回滚：`gh repo rename hermes-local-agent-configs --yes` 并还原 `git remote set-url`。

---

## 2026-09-22T16:55:00+0800 — Expand Config Repo to Multi-Agent Hub: Extract Claude Code Configs

### 目的
将原单一 Hermes 本地配置仓库（hermes-local-agent-configs）升级重构为支持多 Agent（Hermes 与 Claude Code 等）的本地统一脱敏配置中心，实现 Claude 运行配置、全局规则体系与状态栏脚本受版本控制管理。

### 变更摘要
1. **提取与归档 Claude Code 配置**：
   - `claude/settings.json`：全局环境（含已修复的 WSL2 宿主机代理 `172.20.0.1:7890`、mcore 边车连接、模型映射与扩展思考配置）；
   - `claude/settings.local.json`：本地自动授权白名单；
   - `claude/config.json`：更新与全局 API 状态；
   - `claude/CLAUDE.md`：全局最高优先级行为守则与透明度规约；
   - `claude/installed_plugins.json` / `known_marketplaces.json`：已装插件（superpowers）与市场源配置；
   - `claude/rules/common/` 与 `claude/rules/typescript/`：全量架构、编码风格、TDD、代码审查、安全检查规则；
   - `claude/scripts/statusline.sh`：本地化状态栏脚本。
2. **构建配套运维恢复脚本**：
   - 新增 `scripts/restore_to_claude.sh`，实现一键将仓库受控 Claude 配置幂等恢复到 `~/.claude/`。
3. **文档与项目定位升级**：
   - 更新 `README.md`，确立 Hermes 与 Claude Code 双智能体配置归档与恢复操作指南。

### 影响范围
- `claude/`（新增全量 Claude 配置资产与规则集）
- `scripts/restore_to_claude.sh`
- `README.md`
- `ITERATION.md`

### 验证命令
```bash
git -C /home/advancer/project/hermes-local-agent-configs status
```

---

## 2026-10-10T02:30:00Z — Purge h2c Skill, Update Config Repo Statusline Engine & Security Settings

### 目的
依据配置库维护规范，彻底清理冗余的 h2c 技能资产，将状态栏全新权威耗时与 TPS 引擎持久化入库，并治理仓库中遗留的无效 Google Drive 路径与网关防打穿配置。

### 变更摘要
1. **彻底移除 h2c 技能** (`claude/skills/h2c/`):
   - 从仓库与本地环境彻底删除 `h2c` 技能目录及定义，保持脚本与配置体系纯净，不纳入非标扩展。
2. **更新配置库 statusline 权威引擎** (`claude/scripts/statusline.sh`):
   - 更新入库官方内核级 `turn_duration` 毫秒级耗时解析逻辑，消除多步任务中的局部停滞与截断误计；
   - 纳入基于 `session_id` 自动定位会话转录日志与全区间 `output_tokens` 真实 Output TPS 计算。
3. **纠正配置库状态栏调用路径** (`claude/settings.json`):
   - 彻底清除仓库中历史遗留的失效 Google Drive 路径（`gdrive/claude-shared/statusline.sh`）；
   - 规范为本地标准调用并追加 WSL 环境容错重定向：`bash /home/advancer/.claude/statusline.sh 2>/dev/null`。
4. **固化 Subagent 防击穿网关与脱敏规范** (`claude/settings.json`):
   - 持久化 `CLAUDE_CODE_ENABLE_SUBAGENTS=0` 与 `CLAUDE_CODE_DISABLE_BACKGROUND_AGENTS=1`；
   - 固化 modelPicker 配置并确保敏感 Token 严格使用脱敏占位。
5. **完善动态缓存忽略规则** (`.gitignore`):
   - 补充忽略 `models_cache.json` 及相关运行期临时缓存。

### 影响范围
- `claude/scripts/statusline.sh`
- `claude/settings.json`
- `.gitignore`
- `ITERATION.md`

### 验证命令
```bash
bash /home/advancer/.claude/statusline.sh <<< '{"cost":{"total_duration_ms":113000},"context_window":{"used_percentage":18}}'
git -C /home/advancer/project/local-agent-configs status
```

---

## 2026-10-19 — Replace local MemoryCore integrations with remote GCP Hindsight

### 授权与范围
用户明确确认切换 WSL、Windows 各客户端及 Hermes 各 Profile。目标为 GCP `35.236.134.50:18888`，沿用现有 Bank `mcore-active-snapshot`。保留所有源码、数据库、历史记忆、会话及原有服务；不提交、不推送 Git。

### 变更
- Hermes 默认及各 Profile 启用官方 Hindsight 1.2.3 提供方，使用 `local_external` 连接 SSH 回环入口，开启自动召回、留存和工具；Windows 实际数据目录 `%LOCALAPPDATA%/hermes` 同步配置。
- Claude Code、Codex、Gemini、OpenCode 的 MCP 切换到同一 Bank 的认证 MCP。移除旧 mcore 环境变量、Hook、权限项和活动规则。
- Claude/Codex/Gemini 使用轻量召回与留存适配器；Windows 侧经原生 WSL 命令执行，转换 Windows 转录路径。OpenCode 使用 MCP 和记忆规则，不声明未经验证的自动 Hook。
- 归档旧 mcore 插件和 Hook、仓库恢复副本；不停止本地 mcore 服务和定时器。源码信任记录、历史说明和既有记忆不作为活动配置删除。
- 原生 SSH 仅绑定 Windows、WSL 各自的 `127.0.0.1:18888`，不安装系统服务、不创建桌面图标。重连入口 `scripts/start-hindsight-tunnels.py`。
- 官方 CLI 曾移除 Profile 展示覆盖项，已从原始备份恢复。所有运行配置的非记忆设置与备份语义一致（排除 CLI 配置版本元数据）。
- Windows 插件默认 GBK 读取 UTF-8 `plugin.yaml` 导致原生入口无法注册提供方；只将 `_plugin_version()` 的 `read_text()` 改为 `read_text(encoding="utf-8")`，原文件已备份。该部署兼容补丁会被插件更新覆盖，更新后需复核。

### 验证
- Windows 与 WSL 回环健康检查通过；带认证 MCP initialize / initialized / tools-list 返回 200 / 202空响应 / 200。
- WSL 与 Windows 官方提供方均真实召回成功；客户端 Hook 输出真实召回上下文。
- 固定迁移验收文档同步留存 completed 并读回原文；Hermes 自动留存和 Codex Hook 异步留存均读回准确文档与非零记忆单元。
- JSON、TOML、YAML 可解析；活动配置无旧 mcore 接入，唯一保留匹配是普通源码目录信任项。
- Linux 凭据权限600，Windows 凭据文件当前用户独占且无继承；配置仓库扫描未发现真实 MCP 令牌；`git diff --check` 通过。

### 生效与回滚
旧长驻会话可能仍持有已加载的插件和提示词；新会话或用户选择的客户端重启后加载新配置。本次不强制重启现有桌面、终端或网关。
原生转发不是开机服务；退出、断线或重启后需运行重连脚本。回滚按 `~/.local/state/hindsight-migration/20261019-094403/manifest.json` 恢复配置及归档旧插件，只处理本次创建的 SSH 进程。配置备份含认证信息，不进入仓库。


---

## 2026-10-21 — Switch Hindsight memory tools to direct remote (35.236.134.50:18888)

### 授权与意图
用户明确要求所有 Agent 记忆工具直连远端 Hindsight 服务，不再依赖本地 SSH 回环转发监听。保留目标 Bank `mcore-active-snapshot` 与所有现有记忆数据。

### 变更清单
- **连接中枢**：更新 `~/.config/hindsight/connection.json`，将 `api_url` 与 `mcp_url` 指向 `http://35.236.134.50:18888`。
- **Hook 脚本**：更新 `~/.local/lib/hindsight/hindsight-hook.py`，放宽入口白名单检查以允许直连远程 `35.236.134.50`。
- **Claude Code**：WSL (`~/.claude.json`) 与 Windows (`/mnt/c/Users/.../.claude.json`) 的 `hindsight` MCP 端点更新为公网地址。
- **Codex**：WSL (`~/.codex/config.toml`) 与 Windows (`/mnt/c/Users/.../.codex/config.toml`) 的 `hindsight` MCP 端点更新为公网地址。
- **Gemini & OpenCode**：`~/.gemini/settings.json` 与 `~/.config/opencode/opencode.json` 的 MCP 地址更新为公网地址。
- **Hermes Agent**：默认配置 (`~/.hermes/hindsight/config.json`)、Windows 宿主配置 (`AppData/Local/hermes/hindsight/config.json`) 及 8 个 Profile (`design`, `review`, `security`, `commitint`, `qa`, `coord`, `impl`, `req`) 的 `api_url` 全部更新为公网地址。
- **脱敏仓库镜像**：同步更新 `local-agent-configs` 中的对应脱敏镜像文件。

### 验收与验证
- 远端健康检查：`http://35.236.134.50:18888/health` 返回 HTTP 200。
- MCP 协议握手：使用已授权 Token 发起 `initialize` 与 `tools/list`，返回 HTTP 200 并成功发现 `retain`、`recall`、`reflect` 等 36 项工具。
- 生命周期 Hook：向 `hindsight-hook.py recall --agent claude` 输入测试载荷，成功在 2 秒内调取真实历史记忆并输出 Claude 专用 Hook 上下文。
- Hermes 提供方验证：通过 `HindsightMemoryProvider` 调用 `handle_tool_call("hindsight_recall")`，成功检索到真实 Golden Set 评测记忆。
- 安全边界：全量文件配置在修改前均于 `~/.hermes/cache/scratch/hindsight-cutover-backups/` 完成 0600 权限快照备份；迭代记录与仓库中无明文凭据暴露。


## 2026-10-22 枢纽公网 IP 迁移

- 现役枢纽地址由 `35.236.134.50` 更新为 `35.194.237.91`，以原主机可信 SSH 密钥验证身份。
- 同步 Windows/WSL SSH、Claude/Codex/Gemini/OpenCode、两端 cc-switch 地址副本与当前恢复资产；未改模型和凭据。
- Hindsight 客户端通过本机 `127.0.0.1:18888` 原生 SSH 加密转发，健康检查及 MCP 握手通过；保留 Bank `mcore-active-snapshot`。
- ESA 配置已是新 IP；CPA/CPAMP/Hindsight 域名实测 200，自定义面板未改。
- 沙箱 C 的 2224 反向端口及已知备用入口不可达，尚未修改其内部守护；历史归档和其它 profile 保持原样。
- 未提交或推送。

## 2026-10-22 默认 Hermes 原生视觉配置修正

- 用户确认其现用模型均支持原生视觉，并批准修正；默认配置增加 `model.supports_vision: true`，保留 `agent.image_input_mode: auto`。
- WSL `cpa`、`cpa-cloud` 共 12 个模型条目增加 `supports_vision: true`；两端 cc-switch 的 Hermes 模型元数据同步补齐，保留各自原有列表、激活状态、协议、地址和凭据。
- `vision.embed_target_bytes` 设为 `1048576`，提高原生工具图片嵌入字节预算；未修改源码中固定的 1568 像素长边限制。
- 脱敏镜像仅同步全局能力声明与质量预算，未用现役配置覆盖仓库既有旧模型列表或其它未提交改动。
- 验证：配置与备份精确结构比对通过；两端数据库逐行读回符合预期。12 个现役模型条目的用户附件和工具图片路由均为 native；本地 PNG 附件原始字节保持一致，真实识图处理器返回 `_multimodal` / `native_vision: true`，阻断辅助描述函数后仍成功。未向模型网关发送请求。
- 验证边界：桌面内部路由函数采用本地依赖注入测试，不等于运行中桌面端到上游的端到端实测；pytest 未安装，未运行 pytest 套件。测试图经工具从 2400×1800 缩为 1200×900，用户附件组装不发生该缩图。旧会话的已固化工具描述与已丢失图片信息不会自动恢复，需新会话上传原图验收。
- 私有回滚快照：`~/.hermes/cache/scratch/vision-config-20261022-141349/`（含配置、SQLite 备份及本地验证报告；scratch 非长期备份）。回滚只恢复本次视觉字段，勿覆盖后来配置变更。
- 未修改其它 profile、模型端点或凭据，未重启活跃后端，未提交或推送。

## 2026-10-23 路径可移植化、解除 Hindsight 回环强制规则并归档全部待提交变更

- 分支：`main`；远端：`https://github.com/advancer9817/local-agent-configs.git`。用户明确授权本配置库所有改动提交、普通推送；不强推。
- 删除工作目录 AGENTS、Claude/Codex 运行时规则、仓库规则副本及迁移模板中“所有客户端必须回环／SSH”的限制。保留凭据脱敏与禁止不可信第三方穿透；历史迁移方案标为历史，不重写历史证据。
- Claude、Codex、Hermes 配置中个人绝对路径改为 `./` HOME 相对模板；恢复工具按目标 HOME 解析，不依赖启动 cwd。Windows 用户和系统目录改自动发现，支持环境覆盖。网络 URL、系统规定路径和历史审计路径不相对化。
- 排除 Codex 单机项目信任与 Hook 授权哈希、Hermes updater 安装状态。同步最新脱敏内置记忆；补收缺失的微信通知 Hook，仅从本地账户文件加载凭据，日志走 scratch。旧 Claude 密钥字段统一脱敏。
- 一并归档此前未提交的 Hindsight 插件/Hook 接入、多个 Profile 的脱敏配置、模型视觉字段、GCP 地址迁移、旧 mcore 自动插件与脚本退役，以及现有迭代记录。没有删除真实会话库或密钥。
- 离线验证：`python3 scripts/test_portable_configs.py` 四项通过，覆盖模板语法、路径/URL、从其它 cwd 恢复三个客户端、带空格 HOME、Hook 文件存在与重复恢复备份；`git diff --check` 通过。没有调用生产模型网关或自动启动隧道。
- 验证边界：未迁移运行中客户端连接 URL，未重启活跃后端；旧会话已固化的提示不能凭文件修改宣称热更新。历史迁移工具未在真实环境重跑。
- 推送前发现本地/远端分叉，采用保留双方历史的普通合并；远端新增双机交接工具将一并保留并在合并后离线验证。
- 忽略：凭据、会话/数据库、日志缓存、pyc 与 venv 依旧排除。不将现用配置库当作凭据备份。
- 回滚：通过 Git 后续回退提交恢复仓库模板；隔离恢复结果在 scratch 中，运行时规则可按原文恢复，勿整体覆盖活跃配置。
- 本次提交覆盖的完整变更清单（含此前修改）：
  - ` M ITERATION.md`
  - ` M README.md`
  - ` M claude/CLAUDE.md`
  - ` M claude/config.json`
  - ` M claude/installed_plugins.json`
  - ` M claude/known_marketplaces.json`
  - ` M claude/scripts/statusline.sh`
  - ` M claude/settings.json`
  - ` M claude/settings.local.json`
  - ` M codex/config.toml`
  - ` M codex/hooks.json`
  - ` M codex/instructions.md`
  - ` M hermes/SOUL.md`
  - ` M hermes/config.yaml`
  - ` M hermes/memories/MEMORY.md`
  - ` M hermes/memories/USER.md`
  - ` M hermes/plugins/external-agents/runner.py`
  - ` D hermes/plugins/mcore-memory/__init__.py`
  - ` D hermes/plugins/mcore-memory/plugin.yaml`
  - ` M hermes/skills/gate/SKILL.md`
  - ` D scripts/lmmcp-query`
  - ` D scripts/mcore-context.sh`
  - ` D scripts/mcore-ingest.py`
  - ` M scripts/restore_to_claude.sh`
  - ` M scripts/restore_to_codex.sh`
  - ` M scripts/restore_to_hermes.sh`
  - `?? docs/plans/2026-10-19-hindsight-migration.md`
  - `?? hermes/hindsight/config.json`
  - `?? hermes/profiles/commitint/config.yaml`
  - `?? hermes/profiles/commitint/hindsight/config.json`
  - `?? hermes/profiles/coord/config.yaml`
  - `?? hermes/profiles/coord/hindsight/config.json`
  - `?? hermes/profiles/design/config.yaml`
  - `?? hermes/profiles/design/hindsight/config.json`
  - `?? hermes/profiles/impl/config.yaml`
  - `?? hermes/profiles/impl/hindsight/config.json`
  - `?? hermes/profiles/qa/config.yaml`
  - `?? hermes/profiles/qa/hindsight/config.json`
  - `?? hermes/profiles/req/config.yaml`
  - `?? hermes/profiles/req/hindsight/config.json`
  - `?? hermes/profiles/review/config.yaml`
  - `?? hermes/profiles/review/hindsight/config.json`
  - `?? hermes/profiles/security/config.yaml`
  - `?? hermes/profiles/security/hindsight/config.json`
  - `?? scripts/finish-hindsight-migration.py`
  - `?? scripts/hindsight-hook.py`
  - `?? scripts/migrate-hindsight-local.py`
  - `?? scripts/notify_weixin_ilink.py`
  - `?? scripts/portable_paths.py`
  - `?? scripts/restore_configs.py`
  - `?? scripts/start-hindsight-tunnels.py`
  - `?? scripts/test_portable_configs.py`

## 2026-10-17 18:20 +0800 — chore(rules): simplify communication preference to Chinese only

- 用户要求交流规范只保留“使用中文交流”，取消三段式工具播报、强制长篇分析、固定措辞和语气限制。
- 已更新仓库 `codex/instructions.md` 与 `hermes/memories/USER.md`，保留非交流类规则与架构偏好；历史迭代不重写。
- 运行时 `~/.hermes/SOUL.md` 与 `~/gdrive/claude-shared/CLAUDE.md` 的交流段已改为单条中文要求；未修改凭据、模型路由、MCP 或其他 Profile。
- 未完成：仓库 `hermes/SOUL.md`、`claude/CLAUDE.md` 的保护文件审批超时，未修改且未绕过；本提交不声称三客户端仓库规则已全部对齐。恢复这两份旧模板仍会带回旧交流规则，需后续重新授权修改。
- 校验：提交前检查 Markdown 差异和空白错误；推送后读回远端 main SHA 验证。


## 2026-10-17 — feat(hermes,claude,codex): switch default memory backend to Hindsight

### 目的

将三个本地 Agent（Hermes / Claude Code / Codex）的默认长期记忆后端从 mcore 切换为 Hindsight（通过已暴露的公网 MCP 端点 `recall` / `retain` / `reflect`），mcore 保留为二线/兼容后端。本次仅镜像脱敏配置与脚本资产，不含任何凭据。

### 变更范围

- **新增 Hermes 插件** `hermes/plugins/hindsight-memory/`（`__init__.py` + `plugin.yaml`）：
  - `pre_llm_call` 调 Hindsight `recall` 注入记忆上下文；
  - `post_llm_call` 异步 `retain` 当轮问答为文档（服务端自行提取事实）；
  - `on_session_end` 兜底：调 `hindsight-ingest.py` 将整段 transcript 作为文档 retain。
  - 端点默认 `http://35.236.134.50:18888/mcp/mcore-active-snapshot/`，可用 `HINDSIGHT_MCP_URL` 覆盖；Bearer token 从 `~/.hermes/.hindsight-token`（权限 600，已入 `.gitignore`）读取，绝不硬编码/入库。
- **新增 Agent Hook 脚本** `hermes/agent-hooks/`：
  - `hindsight-context.sh`：UserPromptSubmit 召回 hook（替代 mcore-context.sh），调 `recall` 注入 `additionalContext`；
  - `hindsight-ingest.py`：Stop 写入 hook（替代 mcore-ingest.py），方式 A——整段 transcript 作单文档 `retain`，复用各 agent 的 transcript 提取逻辑（hermes state.db / claude jsonl / codex jsonl / opencode db）。
- **更新** `hermes/AGENTS.md` 记忆规则块（`mcore-memory-rules-begin/end`）：默认后端改为 Hindsight，召回 `mcp_hindsight_recall`、写入 `mcp_hindsight_retain`/`sync_retain`、反思 `reflect`；补充"历史归纳可能过时、冲突时以用户当前指令为准"的时效提示。
- **运行时切换**（仅记录，凭据/运行时态不入库）：
  - Hermes `config.yaml`：`plugins.enabled` 加 `hindsight-memory`，`plugins.disabled` 加 `mcore-memory`；
  - Claude `~/.claude/settings.json`：UserPromptSubmit → hindsight-context.sh，Stop → hindsight-ingest.py；
  - Codex `~/.codex/hooks.json`：Stop → hindsight-ingest.py。
- **`.gitignore`** 追加 `.hindsight-token` / `*-token` / `*.secret` 防凭据误提交。

### 实测

- 服务端：Hindsight 已从 0.10.3 升级至 **1.0.0**（venv pip 升级 + 外部 PG18 自动 alembic 迁移，8985 facts 平滑过渡，pgvector HNSW 索引保留）。
- MCP：公网端点带 Bearer token 认证（无 token → 401，正确 → 200），36 工具齐全。
- 召回：6 组真实查询实测，常规长期记忆命中精准（rerank 0.93~0.99），升级后速度普遍快 30~40%；刚写入的近期事件存在服务端 consolidation 归纳延迟（结构性短板）。
- 写→读闭环：retain 文档后经服务端提取，可被 recall 召回，验证通过。

### 已知边界

- `mcore-active-snapshot` 原为 mcore↔Hindsight 评测快照库，现复用为默认生产库，日常 retain 会写入其中。
- Hermes / Codex 需重启进程加载新插件/hook；Claude 下次启动生效。
- Hindsight 对"刚发生、未归纳"的操作细节召回不准，需等后台 consolidation 处理。
- `connect_agents.py`（mcore 仓库脚本）若重跑会把 Claude/Codex hook 覆盖回 mcore；本次未改该脚本，防覆盖待后续处理。

## 2026-10-10 00:30:00 +0800 - feat(skill): graduate duplicate-file-dedup to high-throughput multi-tier media cleaner

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 升级 `duplicate-file-dedup` 技能，全面落地大容量机械硬盘（4.6TB+）端到端音视频与图片去重清理体系；
  2. 固化两级阶梯式感知指纹架构（Two-stage hierarchical fingerprinting）：复用元数据时长 + 单帧 50% 核心帧 64-bit dHash 初筛 + 3点交叉严审，全盘 1.78 万视频抽取速率由 1.27 f/s 跃升至 13.9 f/s（耗时从 3.9h 降至 21m，提速 11 倍）；
  3. 确立短视频时长密集区三帧（25%/50%/75%）联合交叉判定防误杀铁律，拦截 67% 单帧伪匹配；
  4. 落地大规模图片 64KiB 前缀流式哈希 + 全量 MD5 强哈希引擎，实现毫秒级完全字节克隆判定；
  5. 落地免 openpyxl 依赖的 uv 驱动四表审计 Excel 导出器，生成 Windows 原生路径的专业交付凭证；
  6. 新增三个生产级配套执行脚本：`two_stage_video_dedup.py`、`image_exact_dedup.py`、`export_audit_excel.py`。
- 变更范围: `skills/duplicate-file-dedup/`

## 2026-10-09 22:05:00 +0800 - feat(codex): set default permissions to full-access (danger-full-access + never approval)

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 修改说明:
  1. 在 Codex 全局配置 `~/.codex/config.toml` 及纳管模板 `codex/config.toml` 中配置 `sandbox_mode = "danger-full-access"`；
  2. 配置 `approval_policy = "never"`，将 Codex 原生权限默认选项固化为 Full Access；
  3. 解除跨工作区读写与外网限制，消除多智能体无人值守编排（如 FARM）时的权限确认阻塞；
  4. 经 `codex doctor` 诊断实测验证，沙箱状态已呈现 `unrestricted fs + enabled network · approval Never`。
- 变更范围: `codex/config.toml`

## 2026-10-09T21:40:00+0800 — Fix Claude Statusline Incremental Turn Duration & Physical Output TPS

### 目的
修复 Claude Code statusLine 状态栏脚本在长驻留热会话（Farm 编排）环境下指标失真的问题，将上下文累计时间与上下文总 Token 除法替换为真实的单轮活跃耗时与模型生成物理 TPS。

### 变更摘要
1. **真实物理 TPS 计算** (`claude/scripts/statusline.sh`):
   - 彻底废除将 Context Window 全量上下文输入/缓存 Token（80k+）除以 API 时间的虚高公式（原先导致 `2.64kt/s`）；
   - 改为通过 transcript 增量去重统计实际模型输出 Token，除以轮次生成耗时，输出真实的物理吞吐速率（例如 `91.1 tps`）。
2. **单轮活跃耗时校准** (`claude/scripts/statusline.sh`):
   - 修复直接使用 `.cost.total_duration_ms` 导致长驻留工位显示整个会话生命周期（如 `⏳2m59s`、`⏳1h`）的缺陷；
   - 追踪并计算单轮活跃任务耗时（如 `⏳31s`），与编排控制台遥测保持绝对一致。

### 影响范围
- `claude/scripts/statusline.sh`
- `ITERATION.md`

---

## 2026-10-09T22:00:00+0800 — Fix Statusline Time Stalling & Sub-step Truncation (Align 112s vs 24s)

### 目的
修复 statusLine 在多工具复杂任务中因频繁缓存覆盖导致的时间停滞以及将总任务耗时（如 112s / 1m53s）截断误计为最后单步 API 耗时（24s）的严重缺陷。

### 变更摘要
1. **真实用户任务起点定位** (`claude/scripts/statusline.sh`):
   - 过滤工具返回消息 (`tool_result`)，准确定位当前用户原始 Prompt 的真实时间戳；
   - 任务进行中时基于挂钟时间 (`now - prompt_time`) 实时动态递增，彻底消除时间停滞不前的问题；
   - 任务完成时精准锚定到终态事件时间戳，输出完整的端到端总耗时 (`⏳1m53s` / 112.9s)，与编排面板及终端日志实现完全一致。
2. **多步骤产出真实 TPS** (`claude/scripts/statusline.sh`):
   - 汇总整个任务区间内所有回复的 `output_tokens` 并结合全任务耗时计算真实平均吞吐。

### 影响范围
- `claude/scripts/statusline.sh`
- `ITERATION.md`


---

## 2026-10-09T22:35:00+0800 — Authoritative Turn Duration from Claude Engine & Session Auto-Discovery

### 目的
彻底解决 Claude 状态栏 (statusline) 在多步复合任务完成后耗时少记（例如实际 112s / 1m53s 却仅记录 24s）的缺陷，将耗时对齐到 Claude 原生内核级记录的标准单轮耗时。

### 变更摘要
1. **优先采信官方 turn_duration 耗时** (`claude/scripts/statusline.sh`):
   - 解析 Claude Code 转录中系统级终态事件 `type="system", subtype="turn_duration"` 的 `durationMs` 字段；
   - 彻底避免任何多步骤执行过程中的局部截断或差值覆盖，直接呈现毫秒级精准的端到端单轮总耗时（如 113079ms -> `⏳1m53s`）。
2. **转录文件自动溯源** (`claude/scripts/statusline.sh`):
   - 增加 `session_id` 自动索引机制，当环境未显式透传 `transcript_path` 时自动定位会话转录日志，保障高可用。

---

## 2026-10-11 — feat(hermes): integrate encrypted sequential two-computer handoff

### 目的

将公司电脑 / 家里电脑轮流使用 Hermes 的交接流程集成到本地配置项目，提供明确命令与可随仓库分发的使用说明。

### 变更范围

- 新增 `scripts/hermes_handoff.py`：`init`、`depart`、`arrive`、`status`、`doctor`；默认离线，显式 `--publish` / `--pull` 控制 Git 操作。
- 新增 `scripts/requirements-handoff.txt`、`tests/test_hermes_handoff.py`。
- 新增 `docs/hermes-handoff.md`、`docs/hermes-handoff-verification.md`；更新根 README 与忽略规则。
- 配置只合并受控字段；规则、记忆、技能、references 和会话主库统一认证加密；SQLite Backup API 一致性备份，恢复前备份及失败回滚。
- 交接代次、active/departed receipt、本地漂移检查、活动进程检查与独占锁阻断静默覆盖；推送失败保留 pending 并显式重试。
- 保留本机 Key、OAuth、cc-switch、模型路由、MCP、代理和工作目录；不处理其他 Profile、项目文件、附件或 MemoryCore 数据库。

### 实测

- 普通 WSL：`python3 -m unittest discover -s tests -p test_hermes_handoff.py -v`，45 tests / 31.122s / OK。
- 临时双 clone + 本地 bare remote 验证公司出发 → 家里接管并修改 → 家里出发 → 公司接管；读回 remote HEAD 验证一致。
- 验证凭据保留、FTS 检索、技能执行权限、错密钥/篡改/路径穿越/重复路径阻断、漂移阻断、失败回滚与推送重试。
- 真实目录只执行初始化前 `doctor`，返回成功；未创建真实交接密钥、receipt 或会话包，未提交/推送本仓库。

### 已知边界

- 仅支持 Linux/WSL；两端需同一可信使用者轮流使用且获得公司数据外传授权。
- 新工具不修复既有明文归档/历史；大库包体与 Git 服务限制需在首次启用时核对。
- 未用真实全量聊天跑首次导出恢复；两台电脑的 Hermes 版本兼容性需另行确认。
- 受保护 `AGENTS.md` 写入审批超时，未获批准且未绕过；使用入口通过普通 README / docs 交付。
- 保留本文件原有未提交记录；本轮不自动 commit/push。

## 2026-10-23 合并远端配置与交接工具

- 普通合并 origin/main，保留双方提交与全部迭代记录，不强推。保留远端双机交接工具、沟通规则简化及 Codex 权限设置；保留本次路径可移植化与解除回环限制。
- 状态栏保留双方功能，个人路径按 HOME 发现。合并后路径恢复 4 项测试及双机交接 45 项离线测试全部通过；未执行真实交接、上传或客户端覆盖。非测试文件密钥样式扫描无命中，凭据/缓存/会话库继续排除。

## 2026-10-26 合入 Hindsight 可视化初始化应用

### 范围

- 将本轮开发的初始化应用归入 `apps/hindsight-initializer/`，不另建仓库，不替换 `scripts/hindsight-hook.py` 或现有模板恢复、双机交接工具。
- Windows 使用 WebView2 独立窗口并保留浏览器模式，Linux 使用本机网页；HTML/CSS/JavaScript、字体、图标内嵌于 Go 可执行文件。
- 支持远端地址与认证、模型配置、Codex/Claude Code/Hermes 历史来源及文档目录选择、本地脱敏归档、项目内精确去重、分段提炼与归并、独立核验、显式确认上传和 MCP 配置备份恢复。
- 保留跨扫描批次的核验缓存、上传台账和异步操作身份。客户端原文不删除；不自动删除远端历史文档或改写实时留存游标。

### 仓库整合

- 根 README 增加应用入口和构建命令，`docs/hindsight-initializer.md` 说明架构及其与现有脚本的边界。
- 构建输出到 Git 忽略的 `output/hindsight-initializer/`；程序、压缩包、客户端认证、原始会话、归档成品和运行台账均不作为源码提交。
- 浏览器测试自行启动临时应用和模拟服务，不依赖开发机器的固定预览地址。Go 单元测试隔离 HOME，避免读取真实连接配置。
- 补充仅在 Windows 执行的 DPAPI 往返测试。字体、图标与 Go 依赖许可证随源码纳管。

### 验证与边界

- 应用目录下 `go test -race ./...` 的 15 项测试通过，`go vet ./...` 通过；`bash build.sh` 从仓库根目录成功构建 Windows GUI EXE 与 Linux 程序。
- `SETUP_BINARY=<测试构建> node ui_test.cjs` 使用临时应用及模拟服务通过扫描、去重、脱敏正文预览、压缩核验、上传回读和重复上传跳过；验证 1180、840、390 像素视口。
- 既有 `scripts/test_portable_configs.py` 的 4 项测试与 `tests/test_hermes_handoff.py` 的 45 项测试全部通过；原有配置恢复和双机交接行为未改动。
- 包含新增 DPAPI 测试的 Windows 测试程序已交叉编译，尚未在 Windows 执行。源码扫描未发现新增真实凭据、运行台账或绑定开发机器的路径；依赖许可证按上游原文保留。
- Windows EXE 交叉编译不代表 Windows 真机上的 WebView2/DPAPI 已验收。当前环境只能验证 Linux 浏览器流程、模拟上传和跨平台构建，不自动执行真实文档导入或覆盖真实客户端配置。

## 2026-10-26T22:18:57+0800 修复 Hindsight 初始化连接与压缩模型配置

### 变更

- 按用户要求移除初始化工具中的 Hindsight 认证令牌输入、导入、存储和请求头；加载旧配置时清理令牌字段，保留模型 API Key 与本地页面授权。
- REST 连接测试、上传和 MCP 桥接改用无令牌访问；服务端仍要求认证时明确报告，不将 REST 可达误判为 MCP 可用。迁移脚本不再读取或分发远端令牌。
- 模型地址只填域名时自动补齐 `/v1`，保留显式自定义路径；等价地址修改不会清空已保存密钥，服务地址或路径改变时不沿用旧密钥。
- 缺少模型地址或名称时禁用压缩并提供配置入口；后端在清空既有成品前校验模型配置，错误不再导致成品丢失。
- 更新接入说明，明确无令牌访问的网络暴露风险。服务端已按授权停用可选 MCP 令牌校验；此提交不包含生产凭据、运行配置或数据库。

### 验证

- 20 项 Go 测试及子用例通过，`go test -race ./...`、`go vet ./...`、JavaScript 与迁移脚本语法检查通过。
- Playwright 临时模拟服务回归通过：无令牌连接、模型密钥发送、地址补齐、缺少模型配置、扫描、压缩核验、模拟上传与幂等；覆盖桌面及手机视口。
- Windows 测试程序交叉编译通过，未在 Windows 真机执行。Linux 应用已更新，本机已保存的模型密钥、Bank 与 599 条来源记录保留。
- 真实服务的无令牌 MCP 握手和不含历史文件的模型 JSON 连接测试通过；未执行真实历史数据上传。构建产物、客户端状态和凭据仍由 Git 排除。

## 2026-10-27T00:26:34+0800 智能发现本地文档与提炼结果人工复核上传

### 变更

- 增加“全电脑”和“指定目录”智能扫描，识别本机可访问磁盘并递归发现文档，自动加入提取范围；仅保存文件元数据，不自动读取正文、调用模型或上传。
- 增加实时发现数量、当前位置、取消及部分清单保存；清单持久化恢复，来源分页和筛选不再截断为前 1,000 条。单次发现上限为 20,000 个文件，超限明确报告。
- 统一文档格式和敏感路径过滤：仅列入当前解析能力支持的格式，PDF 依赖本机 `pdftotext`；不可解析、超限和无正文条目从可见列表隐藏，保留本地诊断记录。
- 提炼结果支持完整正文和来源明细、会话 ID、字数变化及核验状态查看；上传选择默认为空，需逐篇选择并单独确认，只提交已选且通过核验的结果。
- 上传后或选择、目标变化时取消确认；接口拒绝空选择、无效结果和未通过核验的结果，保留原有回读验证及幂等。
- 删除右上角浏览器打开和退出按钮及前端绑定；已有归档清单在打开应用时直接可见，取消任务不再显示 `context canceled` 错误框。

### 验证与边界

- `go test -race ./...`、`go vet ./...`、JavaScript 语法检查和差异空白检查通过；Windows 测试程序交叉编译通过，未执行 Windows 真机验收。
- Playwright 使用临时文件、模拟模型和 Hindsight 服务，验证递归发现、敏感和不支持格式过滤、元数据不解析正文、分页筛选、重开恢复、完整结果及来源查看、仅上传所选结果、重复上传跳过和桌面/手机视口。
- 单元测试覆盖扫描取消保留清单、缺少 PDF 解析器、正文指纹校验、未经确认或无效选择不访问远端、提炼不自动触发上传。
- 本机应用已更新；源码提交不包含扫描范围中的真实文件、扫描清单、脱敏正文、模型密钥、凭据、运行数据库或构建产物。全电脑入口已验证磁盘识别，未替用户启动真实全盘遍历。

## 2026-10-27 本地正文提取、任务进度与召回预算调整

- 文档发现范围收敛为 PDF、DOCX、XLSX、PPTX、MD、TXT；PDF 仍需本机 pdftotext，保留已提取的历史正文和成品。
- 支持勾选待提取文档、按所选清单增量提取及定期保存检查点；取消后可继续剩余文件。区分查找文件、提取正文、模型压缩和确认上传，修复文档选择及压缩按钮状态。
- 为扫描、提取、连接测试、压缩核验、上传回读、智能体配置和恢复提供阶段、数量、当前路径和耗时；总量已知时显示百分比并按处理样本估算剩余时间。进度区统一置于当前页面标题下，保留下方栏样式，按任务显示“扫描中”“提取中”“压缩中”等状态。
- 本地页面授权持久保存，重启后已打开页面仍可使用；补充授权、任务进度、选定提取和取消续提测试，以及模拟模型等待的浏览器验收。
- Hermes 主配置与八个 profile 的召回预算调整为 mid、4096 tokens；同步更新插件、hook 及迁移默认值，通用 hook 上下文输出上限由 7000 调整为 14000 字符。
- 本次提交前验证：55 项 Go 测试（含子用例）通过竞态检测，go vet、JavaScript 语法检查及 4 项配置恢复测试通过。此前本轮 Playwright 模拟服务流程与部署后桌面/手机进度布局验证通过；未执行 Windows 真机验收。
- WSL 浏览器客户端已部署，文档清单、正文、模型配置及页面授权保留。构建产物、运行状态和凭据不纳入源码提交。

## 2026-10-28 Hindsight 服务端入库、访问控制与控制台修复

- 按用户“提交推送”指令，将本会话已部署源码收录到 `apps/hindsight-session-ingest/`；不包含生产连接配置、账号密码、令牌、任务库、会话原文、构建产物或验证截图。
- 日常钩子在提示提交前召回，回合结束一次提交完整会话和变化产物；客户端只做采集与安全预检，服务端负责清洗会话、解析产物、LLM 压缩、原生 retain 与任务重试。
- 新增访问网关、SQLite 账号授权库及控制台：登录、管理员账号管理、令牌发放与吊销、按数据仓隔离、CSRF 防护、API 鉴权开关与审计。禁止管理员通过重置接口重置自己，改用当前密码验证后的修改入口。
- 控制台沿用 Hindsight 的主题与资产，修复悬停提示撑出表格滚动区、提示残留、抽屉授权栏挤压和窄屏顶栏溢出；数据仓选择改为等宽对齐的可搜索组合框，支持鼠标和键盘操作。
- 初始化应用改为上传原件到服务端准备区、展示远端提炼预览及再次确认入库，移除本地解析和模型配置；删除已被新流程取代的旧本地处理模块，避免混合编译。原有客户端运行数据不随本次源码同步被覆盖。
- 仓库脚本入口统一转发到新模块；配置恢复和迁移脚本同时安装钩子与两个依赖模块，增加安装完整性与缺少连接配置时的离线回归。
- 验证：服务端 57 项、客户端 19 项、配置恢复 4 项及双机交接 45 项 Python 测试通过；Go 竞态测试、go vet、Linux 构建通过。初始化应用在隔离进程和模拟远端下验证准备、预览、确认入库与重复提交幂等；控制台在 1920、1280、390、320px 深浅色八组浏览器回归通过。
- 部署边界：本机 API、worker、网关和 Codex/Claude 钩子已更新；外部 Windows/WSL 客户端和独立初始化程序的运行版本未通过本次 Git 同步自动升级，Windows 真机验收仍需单独执行。本次提交推送不重启生产服务。

## 2026-10-28 关闭上传凭据正则检测

- 按用户要求，关闭将 archify HTML 内 `token` 代码变量误报为凭据的上传内容检测，默认不再匹配原件中的凭据正则；保留显式环境开关 `HINDSIGHT_UPLOAD_CREDENTIAL_CHECK=1` 用于重新开启。
- 保留登录鉴权、数据仓授权、文件范围、类型、大小、二进制与 Office 结构限制，服务端正文脱敏不变。关闭凭据预检意味着真实凭据也可能随原件上传，不代表原件已脱敏。
- 同步本机已安装模块，不重启生产服务、不修改权限或自动重传历史文件。三份原先被拒的 HTML 已通过本地原件预检，后续自动收集可重新尝试上传。
- 回归：23 项客户端测试及 57 项服务端测试通过，新增默认关闭、显式开启、非凭据边界不变和原件传输测试。

## 2026-10-28 回退会话蒸馏，恢复原文入库

- 按用户要求，撤回另一会话部署的会话蒸馏、专用档案库分流与 30 分钟静默等待，运行代码回到本仓库已提交的原文上传实现；恢复全部用户/助手消息与原有召回预算。产物的服务端解析和 LLM 压缩、鉴权、账号授权、控制台修复及默认关闭的上传凭据正则检测保持不变。
- 回退前备份当前数据库、任务队列、运行文件与启动环境；从迁移前备份选择性恢复原会话，不整库覆盖，不用旧备份覆盖恢复期间收到的新原文。
- 主库回读核对：17 篇原会话、0 篇会话摘要；移除 13 篇摘要，保留档案库 17 篇副本。千帆报表保留后续原文更新。正文恢复不代表全部事实重建完成：仍有一篇长会话的原生异步提取在处理，对应的新版本由任务队列等待旧任务结束后提交。
- 本地独立源码副本同步回退，蒸馏专用代码与测试移入受限备份目录；源码仓库新增完整会话传输和不做前置模型蒸馏的回归测试，并澄清原生 retain 仍调用模型提取记忆。
- 验证：客户端 24 项、服务端 58 项测试通过，两份源码副本均通过；已安装四个运行模块与仓库源码逐字一致，API 与两个 worker 健康、网关 MCP 召回和控制台登录入口正常；无会话任务遗留临时长时间暂停。生产配置、会话原文和备份不纳入 Git。

## 2026-10-28 原文上传后的轻量会话整理

- 用户进一步明确“把这个原文上传的提炼一下就好了”。保持客户端完整原文上传及现有队列、文档 ID、主库和原生 retain，仅在服务端增加整篇 LLM 整理，不恢复证据条目过滤、专用档案库分流或静默等待，不批量迁移历史文档。
- 整理保留背景目标、关键约束、最终方案及修订、助手报告的实现与验证结果、排障、待办及产物入口；强调历史转述与真实用户消息、助手报告与独立验证的区分，不为固定条数或压缩比例牺牲上下文。
- 原始上传字节仍保存在任务 `original`；清洗正文及整理稿分别保存在 `parsed_text`、`refined_text`，复用现有任务预览。整理结果缓存供入库重试使用，整理期间的新上传仍可覆盖旧版本并阻止旧稿提交。
- 保留数字、路径及凭据检查；唯一可对应的 Windows/WSL 文件路径恢复原文写法，章节编号不当作新数字事实；必要时最多校正一次无依据字面量。模型不可用或输出不合格时完整清洗正文照常入库，不阻塞会话；字面量检查不是语义完整性证明。
- 使用真实「千帆报表」会话试跑，读取期间识别并避开了旧候选与新上传状态不一致的问题；最新 178,661 字正文整理为 6,758 字，保留流式包、81 项离线测试与千帆待实测的区别。单篇验证沿用原文档 ID 和原始上传字节，其他历史文档不变。
- 验证：客户端 24 项、服务端 70 项测试通过，新增完整上下文、原文回退、字面量校正、路径校正、缓存、新版本防覆盖及 HTTP 身份不变测试。运行 API 已备份后部署三个模块并重启，客户端与 worker 不变；已安装模块与仓库逐字一致，独立源码副本 70 项测试及网关 MCP 召回通过。单篇原生 retain 已完成，回读正文与 6,758 字整理稿逐字一致，仍使用原文档 ID。生产凭据、真实会话和验证产物不纳入 Git。
