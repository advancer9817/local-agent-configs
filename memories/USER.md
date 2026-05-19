Hands-on architect; prefers Chinese, HTTP services, modular portable code, URL-based MCP. Expects Hermes to be a general-purpose entrypoint/multi-agent router: use SDLC profiles for dev tasks, but route research/docs/knowledge/ops/creative/automation/data work via appropriate tools or agents without forcing SDLC.
§
User prefers proactive durable learning after sessions and requires all long-term memories to be written to lmmcp/MCP, not only Hermes built-in memory. Save relevant preferences/knowledge to MCP first or in sync; update class-level skills for reusable procedures.
§
User prefers exported documents and deliverables to be placed in C:\Users\e-pengyang.DU\Desktop\output (WSL path /mnt/c/Users/e-pengyang.DU/Desktop/output).
§
User prefers Hermes SDLC routing where design and review roles delegate to Claude Code CLI; implementation development is done by Codex CLI, while Claude Code performs testing/verification of Codex-produced code. Profile model assignments: default/coord/design/qa/review = claude-sonnet-4-6 (custom:apikeyfun); req/commitint = deepseek-v4-flash (deepseek); impl = gpt-5.5 (openai-codex); security = claude-opus-4-7-thinking (custom:apikeyfun).
§
用户的项目默认放在 /home/advancer/project/。
§
用户的 git 拉取项目也默认放在 /home/advancer/project/。
§
用户希望项目可被他人复用；实现时要优先考虑兼容性、通用性、可移植部署脚本，以及运行命令的执行目录。路径、IP、用户名、项目根目录等不应硬编码，应支持参数、环境变量或自动发现。