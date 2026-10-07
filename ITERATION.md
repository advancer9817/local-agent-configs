# hermes-local-agent-configs 迭代记录

本文件记录随仓库提交一起推送的项目迭代信息，用于追溯每次变更的范围、原因与提交记录。

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
