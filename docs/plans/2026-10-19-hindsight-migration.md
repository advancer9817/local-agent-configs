# 本地 mcore 接入迁移至 GCP Hindsight

> 历史迁移方案，非现行接入约束。回环／SSH 不再强制；部署以用户当前选择和有效配置为准。下文授权描述仅对应当时迁移，不覆盖后续明确授权。

**授权**：用户已确认 WSL、Windows、多客户端及 Hermes 各 Profile 的本地接入替换。允许可回滚备份、原生 SSH 回环转发、插件安装与连接验收。不授权停止远端服务、删除数据库、Git 提交或推送。

**目标**：GCP 35.236.134.50:18888，保留 Bank `mcore-active-snapshot`。各客户端只连接本地回环，经原生 SSH 加密到远端；不安装后台系统服务、不创建桌面图标。

## 执行与验收

- 保存原配置、规则、旧插件与 Hook 至 `~/.local/state/hindsight-migration/`，认证副本权限 600，目录 700。
- 验证 Windows 和 WSL 回环转发 `/health`、带认证 MCP initialize → initialized → tools/list。不得打印令牌。
- Hermes 使用官方 Hindsight 插件，配置 `local_external` 指向回环地址与现有 Bank，启用自动召回、自动留存及工具。保留本地内置记忆；移除旧 mcore 插件和 MCP 接入，清除旧委派记忆配置。
- Claude/Codex/Gemini/OpenCode 接入同一个 Bank 的 MCP；移除 mcore 专用环境变量、权限项、Hook、通知及活动规则。需要自动能力的客户端采用经过验证的 Hindsight 薄适配器，保持其他 Hook 不变。
- 同步脱敏配置仓库与 ITERATION.md，不复制密钥、不提交或推送。保留源码、项目历史、数据库、会话、历史技能说明。
- 扫描所有目标活动配置：旧 mcore 接入不得残留。解析 JSON/TOML/YAML，独立验证各连接定义与权限，验证官方提供方加载；真实召回/留存验收使用明确标识的迁移事实并读回，不伪造模型响应。

## 回滚

按备份 manifest 恢复被改文件，将旧插件从归档恢复。只结束本次创建且身份核对的 SSH 进程，不影响原有服务。转发生命周期和新会话生效条件必须如实交付。
