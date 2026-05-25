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
