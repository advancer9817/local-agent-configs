User installed Node.js via nvm (LTS v24.15.0) and Codex CLI (v0.130.0) inside WSL. Both Claude Code (v2.1.123) and Codex are available for coding agent orchestration. nvm LTS default is set in .bashrc.
§
USER ENVIRONMENT: WSL on Windows, home=/home/advancer, timezone=Asia/Shanghai. Shell: zsh + Oh My Zsh + powerlevel10k theme. Terminal tools: eza (ls replacement), zsh-syntax-highlighting, zsh-autosuggestions.
§
AI AGENT STACK: Codex CLI v0.130.0 (gpt-5.5 via local proxy :15721), Claude Code v2.1.123, Hermes Agent. local-memory-mcp project: /home/advancer/.agent-memory/local-memory-mcp. Ollama 0.23.2 runs at http://127.0.0.1:11434 with nomic-embed-text:latest; local-memory-mcp semantic provider defaults to Ollama 768-dim with hashing fallback via env.
§
KNOWN ISSUE — WSL NETWORK: WSL internal network latency is significantly higher than Windows host for API calls. DeepSeek (api.deepseek.com) and openai-codex (chatgpt.com/backend-api/codex) both suffer intermittent APIConnectionError in WSL, while same models work fine on Windows host. This is the user's primary pain point.
§
CLAUDE CODE SETTINGS: Uses xuedingtoken.com proxy, model=claude-haiku-4-5-20251001, effort=low, bypass permissions, dark-ansi theme. MCP servers: openmemory at localhost:8765 and local_memory stdio at /home/advancer/.agent-memory/local-memory-mcp/local_memory_mcp.py.
§
CODEX SETTINGS: Model=gpt-5.5 via base_url=http://127.0.0.1:15721/v1. Trusted dirs include WSL /home/advancer and Windows project dirs. MCP: openmemory HTTP + local_memory stdio. Apikeyfun custom provider exposes Claude Haiku/Sonnet/Opus 4.x variants, including thinking models.
§
ATTEMPTED INSTALLS: OpenCode CLI was installed via curl | bash but 'opencode' command not found after installation — likely PATH not sourced or install path issue.
§
Python environment in WSL: system python3 is 3.10 and initially lacked pip/venv; python3.10-venv and python3-pip were installed via apt. A user-local Python 3.11 exists at /home/advancer/.local/bin/python3.11 and works for packages requiring >=3.11.
