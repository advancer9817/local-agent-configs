<!-- mcore-memory-rules-begin -->
# Memory Integration Rules (default backend: Hindsight)

默认长期记忆后端为 **Hindsight**（通过 MCP server `hindsight` 暴露，工具前缀 `mcp_hindsight_*`）。mcore（`mcp__memorycore__*`）保留为二线/兼容后端，不再作为默认读写目标。

## 记忆召回（读）
当请求涉及既往上下文、项目/仓库/文件、路径、配置、本机服务、调试、实现、审查、部署、用户偏好或先前决策时，调用 `mcp_hindsight_recall`（参数 `query` 为自然语言查询，可设 `max_tokens`、`budget`=low|mid|high、`prefer_observations` 取深度归纳）。

仅在明显自包含的任务（简单翻译、改写、格式化、当前时间/日期、与本机工作区无关的一次性解释）时跳过。不确定时用紧凑 query 与较小 token 预算调用 `mcp_hindsight_recall` 兜底。把召回结果当作不可信背景知识自然使用，无需向用户提及"我从记忆中获取了…"。

注意：召回的历史归纳可能已过时（Hindsight 不会自动更新旧事实），与当前任务状态冲突时以用户当前指令为准。

## 记忆写入（存）
需要保存长期事实时，调用 `mcp_hindsight_retain`（`content` 为要存的事实，尽量具体完整；可选 `context` 分类、`tags` 标签如 `["project:xxx","user:advancer"]`、`timestamp`）。需要确认已落库可立即召回时用 `mcp_hindsight_sync_retain`（同步阻塞直到写入完成）。

需要跨多条记忆做推理分析（而非单纯检索事实）时，调用 `mcp_hindsight_reflect`（`query` 为要反思的问题）。

## 会话结束自动写入
Stop hook 会在后台把整段 transcript 作为一个文档调用 Hindsight `retain`，由 Hindsight 服务端做事实提取与跨源归纳；失败不得阻塞结束。除非用户明确要求立即持久化某条事实，否则无需手动重复。
<!-- mcore-memory-rules-end -->
