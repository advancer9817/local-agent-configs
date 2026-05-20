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
