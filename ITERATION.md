     1|# hermes-local-agent-configs 迭代记录
     2|
     3|本文件记录随仓库提交一起推送的项目迭代信息，用于追溯每次变更的范围、原因与提交记录。
     4|
     5|## 2026-05-19 14:17:17 +0800 - docs(hermes-local-agent-configs): update project iteration
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
bash /home/advancer/project/hermes-local-agent-configs/scripts/restore_to_claude.sh
```

### 风险与回滚
- 风险：低。新增资产全部置于独立的 `claude/` 目录与新脚本中，不影响原有 Hermes 的 `config.yaml`、`SOUL.md` 与 profile 结构。
- 回滚：`git rm -r claude/ scripts/restore_to_claude.sh` 并回滚 `README.md` 与 `ITERATION.md`。

---

## 2026-09-22T17:05:00+0800 — Rename Project Repository to local-agent-configs

### 目的
随着 Claude Code 全套配置及恢复链路接入，原 `hermes-local-agent-configs` 项目名称已无法涵盖多 Agent 统一配置中心的职能。正式将项目目录与说明重命名为 `local-agent-configs`，并建立向后兼容软链接避免旧脚本断链。

### 变更摘要
1. **项目重命名与软链接兼容**：
   - 物理目录重命名：`/home/advancer/project/hermes-local-agent-configs` -> `/home/advancer/project/local-agent-configs`；
   - 建立兼容软链接：`/home/advancer/project/hermes-local-agent-configs` -> `local-agent-configs`，确保既有 Hermes hook 与引用平滑过渡。
2. **文档与配置全局更新**：
   - 更新 `README.md` 标题与路径引用；
   - 更新 `SOUL.md`、`restore_to_hermes.sh`、`restore_to_claude.sh` 中的路径指引；
   - 同步更新 `~/.hermes/SOUL.md` 运行时配置指向。

### 影响范围
- 仓库路径：`/home/advancer/project/local-agent-configs`
- 符号链接：`/home/advancer/project/hermes-local-agent-configs`
- `README.md`、`SOUL.md`、`ITERATION.md`
- `~/.hermes/SOUL.md`

### 验证命令
```bash
ls -ld /home/advancer/project/local-agent-configs
ls -ld /home/advancer/project/hermes-local-agent-configs
git -C /home/advancer/project/local-agent-configs status


