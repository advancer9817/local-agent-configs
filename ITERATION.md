# hermes-local-agent-configs 迭代记录

本文件记录随仓库提交一起推送的项目迭代信息，用于追溯每次变更的范围、原因与提交记录。

## 2026-05-19 14:17:17 +0800 - docs(hermes-local-agent-configs): update project iteration

- 项目: `hermes-local-agent-configs`
- 分支: `main`
- 远端: `https://github.com/advancer9817-crypto/hermes-local-agent-configs.git`
- 关联提交: `0245bf312750c0b711d784905e3c2c9060d53809`
- 提交时间: `2026-05-19 14:13:58 +0800`
- 提交作者: `advancer9817-crypto <advancer9817-crypto@users.noreply.github.com>`

### 迭代说明

```text
- config.yaml                           | 10 +---------
- memories/MEMORY.md                    |  2 +-
- profiles/commitint/config.yaml        | 10 +---------
- profiles/commitint/memories/MEMORY.md |  2 +-
- profiles/coord/config.yaml            | 10 +---------
- profiles/coord/memories/MEMORY.md     |  2 +-
- profiles/design/config.yaml           | 10 +---------
- profiles/design/memories/MEMORY.md    |  2 +-
- profiles/impl/config.yaml             | 10 +---------
- profiles/impl/memories/MEMORY.md      |  2 +-
- profiles/qa/config.yaml               | 10 +---------
- profiles/qa/memories/MEMORY.md        |  2 +-
```

### 修改范围统计

```text
config.yaml                           | 10 +---------
 memories/MEMORY.md                    |  2 +-
 profiles/commitint/config.yaml        | 10 +---------
 profiles/commitint/memories/MEMORY.md |  2 +-
 profiles/coord/config.yaml            | 10 +---------
 profiles/coord/memories/MEMORY.md     |  2 +-
 profiles/design/config.yaml           | 10 +---------
 profiles/design/memories/MEMORY.md    |  2 +-
 profiles/impl/config.yaml             | 10 +---------
 profiles/impl/memories/MEMORY.md      |  2 +-
 profiles/qa/config.yaml               | 10 +---------
 profiles/qa/memories/MEMORY.md        |  2 +-
 profiles/req/config.yaml              | 10 +---------
 profiles/req/memories/MEMORY.md       |  2 +-
 profiles/review/config.yaml           | 10 +---------
 profiles/review/memories/MEMORY.md    |  2 +-
 profiles/security/config.yaml         | 10 +---------
 profiles/security/memories/MEMORY.md  |  2 +-
 18 files changed, 18 insertions(+), 90 deletions(-)
```

### 文件变更清单

```text
M	config.yaml
M	memories/MEMORY.md
M	profiles/commitint/config.yaml
M	profiles/commitint/memories/MEMORY.md
M	profiles/coord/config.yaml
M	profiles/coord/memories/MEMORY.md
M	profiles/design/config.yaml
M	profiles/design/memories/MEMORY.md
M	profiles/impl/config.yaml
M	profiles/impl/memories/MEMORY.md
M	profiles/qa/config.yaml
M	profiles/qa/memories/MEMORY.md
M	profiles/req/config.yaml
M	profiles/req/memories/MEMORY.md
M	profiles/review/config.yaml
M	profiles/review/memories/MEMORY.md
M	profiles/security/config.yaml
M	profiles/security/memories/MEMORY.md
```



## 2026-05-19 17:37:35 - Sync local Hermes agent configs

### 目的
- 将当前本机 Hermes Agent 配置、General Multi-Agent Router SOUL、SDLC role profiles、profile memories/reference 文档导出到本仓库，形成可版本化的本地配置备份。

### 变更摘要
- 更新根配置：`config.yaml`、`SOUL.md`、`memories/`。
- 更新 profiles：`coord`、`req`、`design`、`impl`、`qa`、`review`、`security`、`commitint` 的 `config.yaml`、`SOUL.md` 与 memories。
- 更新 `PROFILE_LIST.txt`、`README.md`、`.env.example`、`.gitignore`、`references/sdlc-role-profiles.md`、`scripts/restore_to_hermes.sh`。
- 所有 secret-like 字段已写为 `<REDACTED>`；未导出 `.env` 真实值、`auth.json`、sessions、logs、state DB、cache、venv。

### 验证
- `git diff --check` 通过。
- YAML 解析校验通过：root + 8 个 profile config 均可解析。
- 敏感信息扫描通过：未发现未脱敏的 api key/token/secret/password/private key 模式。

### 风险与回滚
- 风险：该仓库只包含脱敏配置，恢复后仍需手动配置 `.env` 和 auth 凭证。
- 回滚：使用本 commit 前版本，或用 `scripts/restore_to_hermes.sh` 恢复时生成的 `$HERMES_HOME/backups/restore_*` 备份回退。

### Commit
- `chore: sync sanitized hermes local configs`
