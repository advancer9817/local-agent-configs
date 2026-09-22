# Codex Agent Instructions

## lmmcp / mcore 记忆系统

你有访问 `local_memory` / `mcore` MCP server 的权限（http://127.0.0.1:8318/mcp）。

**每次收到用户问题时，在回答之前必须执行以下步骤：**

1. 调用 `memory_context` 工具，task 参数设为用户问题，token_budget=1200
2. 调用 `memory_search` 工具，query 参数设为用户问题，limit=5
3. 如果返回了相关记忆，将其作为背景知识参考，在回答中体现

**回答结束后，执行以下步骤：**

4. 调用 `memory_ingest` 工具，将本轮 user 问题和 assistant 回答作为 messages 传入，user_id="advancer"

这样可以确保你的回答基于历史上下文，并且每次对话都会积累到记忆库中。

## 工具调用示例

查询记忆：
```
memory_context(task="用户的问题", token_budget=1200)
memory_search(query="用户的问题", limit=5)
```

ingest 回答：
```
memory_ingest(messages=[
  {"role": "user", "content": "用户问题"},
  {"role": "assistant", "content": "你的回答"}
], user_id="advancer")
```

## 注意事项

- 记忆中枢边车服务运行在 http://127.0.0.1:8318/mcp
- 如果 memory_context 返回空或服务不可用，直接回答，不要报错
- ingest 步骤是后置的，不影响回答质量，失败时静默跳过
