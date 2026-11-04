#!/usr/bin/env bash
# hindsight-context.sh — UserPromptSubmit hook: recall from Hindsight and inject as additionalContext.
# Replaces the mcore memory_context hook. Calls Hindsight MCP `recall`.
# Always exits 0; failure must never block the agent.
set -uo pipefail

HINDSIGHT_URL="${HINDSIGHT_MCP_URL:-http://35.236.134.50:18888/mcp/agent-memory/}"
TOKEN_FILE="${HINDSIGHT_TOKEN_FILE:-$HOME/.hermes/.hindsight-token}"
AGENT="${MCORE_AGENT_ID:-claude}"

TOKEN=""
[ -f "$TOKEN_FILE" ] && TOKEN="$(cat "$TOKEN_FILE" 2>/dev/null || true)"

STDIN_JSON="$(cat)"

PROMPT="$(printf '%s' "$STDIN_JSON" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    data = {}
tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}
prompt = (
    tool_input.get("prompt")
    or data.get("prompt")
    or data.get("user_prompt")
    or data.get("message")
    or data.get("input")
    or extra.get("user_message")
    or ""
)
print(str(prompt))
' 2>/dev/null || true)"

HOOK_EVENT="$(printf '%s' "$STDIN_JSON" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    data = {}
print(str(data.get("hook_event_name") or data.get("hookEventName") or ""))
' 2>/dev/null || true)"

touch /tmp/hindsight-session-mark 2>/dev/null || true

[ -z "$PROMPT" ] && exit 0

AUTH_HEADER="Authorization: Bearer ${TOKEN}"

INIT_PAYLOAD='{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hindsight-context-hook","version":"1.0"}}}'
INIT_RESPONSE="$(curl -sS -i --noproxy '*' --max-time 4.0 -X POST "$HINDSIGHT_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "$AUTH_HEADER" \
  -d "$INIT_PAYLOAD" 2>/dev/null || true)"

SESSION_ID="$(printf '%s' "$INIT_RESPONSE" | awk -F': ' 'tolower($1)=="mcp-session-id"{gsub(/\r/,"",$2); print $2; exit}')"
[ -z "$SESSION_ID" ] && exit 0

PAYLOAD="$(python3 -c '
import json, sys
query = sys.argv[1][:500]
payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "recall",
        "arguments": {"query": query, "max_tokens": 4096, "budget": "mid"},
    },
}
print(json.dumps(payload, ensure_ascii=False))
' "$PROMPT" 2>/dev/null || true)"

[ -z "$PAYLOAD" ] && exit 0

RESPONSE="$(curl -sS --noproxy '*' --max-time 8.0 -X POST "$HINDSIGHT_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "$AUTH_HEADER" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d "$PAYLOAD" 2>/dev/null || true)"

CACHE_FILE="/tmp/hindsight-last-context-${AGENT}.cache"

emit_context() {
  python3 -c '
import json, sys
context = sys.argv[1]
event = sys.argv[2]
if event == "pre_llm_call":
    payload = {"context": context}
else:
    hook_event_name = "BeforeAgent" if event == "BeforeAgent" else "UserPromptSubmit"
    payload = {
        "hookSpecificOutput": {
            "hookEventName": hook_event_name,
            "additionalContext": context,
        }
    }
print(json.dumps(payload, ensure_ascii=False))
' "$1" "$2" 2>/dev/null || true
}

[ -z "$RESPONSE" ] && {
  [ -f "$CACHE_FILE" ] && CONTEXT="$(cat "$CACHE_FILE" 2>/dev/null || true)" || CONTEXT=""
  [ -z "$CONTEXT" ] && exit 0
  emit_context "$CONTEXT" "$HOOK_EVENT"
  exit 0
}

CONTEXT="$(printf '%s' "$RESPONSE" | python3 -c '
import json, sys
try:
    body = sys.stdin.read()
    raw = body.strip()
    for line in body.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            break
    resp = json.loads(raw)
    content = resp.get("result", {}).get("content", [])
    text = content[0].get("text", "") if content else ""
    try:
        inner = json.loads(text)
    except Exception:
        inner = {"context": text}
    # Hindsight recall returns structured results; prefer a readable context field,
    # otherwise fall back to the raw text payload.
    ctx = inner.get("context") or inner.get("text") or ""
    if not ctx and isinstance(inner, dict):
        # Build a compact digest from recalled memories if present.
        mems = inner.get("memories") or inner.get("results") or []
        if isinstance(mems, list) and mems:
            lines = []
            for m in mems:
                if isinstance(m, dict):
                    t = m.get("content") or m.get("text") or m.get("memory") or ""
                    if t:
                        lines.append("- " + str(t).strip())
            ctx = "\n".join(lines)
    if not ctx and text.strip():
        ctx = text.strip()
    if str(ctx).strip():
        print(str(ctx))
except Exception:
    pass
' 2>/dev/null || true)"

[ -z "$CONTEXT" ] && exit 0

printf '%s' "$CONTEXT" > "$CACHE_FILE" 2>/dev/null || true

emit_context "$CONTEXT" "$HOOK_EVENT"

python3 -c '
import sys
ctx = sys.argv[1]
lines = ctx.splitlines()
rec_count = sum(1 for line in lines if line.strip().startswith("- "))
tok_est = max(1, len(ctx) // 4)
if rec_count > 0:
    sys.stderr.write(f"\033[32m🎯 [hindsight] 上下文就绪: 召回 {rec_count} 条 (约 {tok_est} Token)\033[0m\n")
' "$CONTEXT" 2>/dev/null || true

exit 0
