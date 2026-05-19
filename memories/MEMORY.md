User installed Node.js via nvm (LTS v24.15.0) and Codex CLI (v0.130.0) inside WSL. Both Claude Code (v2.1.123) and Codex are available for coding agent orchestration. nvm LTS default is set in .bashrc.
§
USER ENVIRONMENT: WSL on Windows, home=/home/advancer, timezone=Asia/Shanghai. Shell: zsh + Oh My Zsh + powerlevel10k theme. Terminal tools: eza (ls replacement), zsh-syntax-highlighting, zsh-autosuggestions.
§
§
KNOWN ISSUE — WSL NETWORK: WSL internal network latency is significantly higher than Windows host for API calls. DeepSeek (api.deepseek.com) and openai-codex (chatgpt.com/backend-api/codex) both suffer intermittent APIConnectionError in WSL, while same models work fine on Windows host. This is the user's primary pain point.
§
§
§
lmmcp = local-memory-mcp 记忆项目。路径: /home/advancer/.agent-memory/local-memory-mcp (运行时) / /home/advancer/project/local-memory-mcp (源码)。SSE端口:8318，所有agent用 http://127.0.0.1:8318/sse。systemd user服务 lmmcp.service 已enabled+linger，开机自启。快捷脚本: /home/advancer/.local/bin/lmmcp [start|stop|restart|status|log|enable|disable]。tests 105/105.
§
CPA Kiro streaming fix: when the OpenAI→Anthropic stream translator re-emits message_start for every content_block_delta, fix by patching kiro_executor.go to emit Anthropic SSE events directly (bypassing buildOpenAIStreamChunk + TranslateStream). The fix is in the local-ai-proxy-gateway-ops skill under "Kiro streaming fix".
§
Hermes default was changed on 2026-05-19 from SDLC-only Router to General Multi-Agent Router v4.2. Default model is custom:apikeyfun/claude-sonnet-4-6. coord/design/impl/qa/review/security/commitint SOUL contracts were updated. Backup: /home/advancer/.hermes/backups/router_v42_20260519_160119. MCP memory ID: cc954425-dc2e-4847-9de6-3cff1947638c.