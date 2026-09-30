# External Agents Plugin (`external-agents`) Specification

## 1. 核心目标与定位
为 Hermes 提供对本地已安装的 **Claude Code CLI** (`/usr/local/bin/claude`) 与 **OpenAI Codex CLI** (`/usr/local/bin/codex`) 的原生编排能力。
让 Hermes 具备通过工具调用（Model Tool）或用户会话斜杠命令（Slash Command）委托外部专业 Coding Agent 执行代码编写、重构、排障与评审，并在任务完成后自动捕获并回传精准的 Git Diff 审计数据。

## 2. 核心架构设计

### 2.1 模块划分与职责
插件目录落地于 `~/.hermes/plugins/external-agents/`：
```text
external-agents/
├── plugin.yaml           # 插件清单与元数据定义
├── __init__.py           # 插件入口 register(ctx)，挂载工具与斜杠命令
├── runner.py             # 核心进程调度器：执行参数拼接、超时截断、日志捕获与脱敏
├── git_tracker.py        # Git 审计模块：变更前后状态对比、文件列表与 diff-stat 提取
└── schemas.py            # 工具入参与返回值 Schema 定义
```

### 2.2 核心流程与数据流
```text
Hermes Agent / 用户斜杠命令
             │
             ▼
    [schemas & __init__.py]
             │ 校验参数 (prompt, workdir, timeout, sandbox)
             ▼
    [git_tracker.py] ── 记录执行前工作区状态 (git status & head)
             │
             ▼
      [runner.py]    ── 构造安全命令，启动非交互执行进程
             │          ├─ Claude: claude -p "<prompt>" --dangerously-skip-permissions
             │          └─ Codex:  codex exec "<prompt>" --sandbox <sandbox>
             │          (实时监控输出，严防悬挂与死锁)
             ▼
    [git_tracker.py] ── 采集执行后差异：新增/修改文件、diff --stat 与补丁摘录
             │
             ▼
     标准 JSON 回显 ──> Hermes 上下文 (包含 success, exit_code, diff_stat, summary)
```

## 3. 接口规范与参数设计

### 3.1 工具一：`claude_code_exec`
- **用途**：调用 Claude Code 自动化执行重构、复杂长上下文代码阅读、特性开发或单测补充。
- **参数列表**：
  - `prompt` (string, required): 委派给 Claude Code 的具体任务要求与技术约束。
  - `workdir` (string, optional, 默认当前目录): 执行任务的工作目录路径。
  - `allowed_tools` (string, optional): 允许 Claude 使用的工具子集（如 `"Read,Edit,Bash"`）。
  - `danger_skip_permissions` (boolean, optional, 默认 true): 非交互模式下是否自动跳过权限提示（采用 `--dangerously-skip-permissions` 或 `--permission-mode bypassPermissions` 确保免阻断）。
  - `timeout` (integer, optional, 默认 300, 范围 10~1800): 进程执行超时秒数。

### 3.2 工具二：`codex_exec`
- **用途**：调用 OpenAI Codex CLI 自动化执行定向任务、代码审查或快速机械化改动。
- **参数列表**：
  - `prompt` (string, required): 委派给 Codex 的指令内容。
  - `workdir` (string, optional, 默认当前目录): 执行目录（必须是 git 仓库，非 git 仓库可自动初始化）。
  - `sandbox` (string, optional, 默认 `"workspace-write"`): 沙箱模式，可选 `read-only`, `workspace-write`, `danger-full-access`。
  - `timeout` (integer, optional, 默认 300, 范围 10~1800): 执行超时秒数。

### 3.3 标准化返回值 (Unified Return Envelope)
所有工具处理函数均以 JSON 字符串返回：
```json
{
  "success": true,
  "agent": "claude-code",
  "exit_code": 0,
  "duration_s": 15.2,
  "workdir": "/home/advancer/project/demo",
  "files_changed": [
    "src/utils.py",
    "tests/test_utils.py"
  ],
  "diff_stat": "2 files changed, 28 insertions(+), 4 deletions(-)",
  "diff_summary": "...",
  "output": "...",
  "error": null
}
```

## 4. 边界处理与安全防御
1. **防止交互挂死**：
   - Claude Code 运行必须严格包含 `-p`（非交互打印输出模式）并设置确切的超时保护（Python `subprocess.Popen` / `communicate(timeout=...)`）；
   - Codex 运行严格使用 `codex exec`，避免进入交互 REPL。
2. **Git 仓库强制校验**：
   - 若目标 `workdir` 不是 Git 仓库，自动预先探测；对于强制需要 Git 的 Codex，若非 Git 仓库则给予清晰友好的错误返回，不导致底层崩溃。
3. **凭据安全与脱敏**：
   - 过滤与清洗标准输出中的敏感凭据与 API Key（对齐 SOUL.md 红线）。
4. **斜杠命令扩展**：
   - 注册 `/claude <prompt>` 与 `/codex <prompt>` 会话命令，供用户在终端或桌面聊天框直接派发任务。

## 5. 测试与验证方案
1. **单元测试 (`tests/test_plugin.py`)**：
   - Schema 校验与参数解析测试；
   - Git 追踪模块（`git_tracker.py`）针对临时 Git 仓库的变更探测准确度测试；
   - Runner 模块命令拼装与超时模拟测试。
2. **集成与端到端测试**：
   - 在临时 Git 目录中触发真实 CLI 探活（例如 `claude -p "echo hello" --version` 与 `codex --version`）；
   - 启用至 `~/.hermes/config.yaml` 并通过 Hermes 探针校验其已被注册为可用 Toolset。
