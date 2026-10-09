#!/bin/bash
input=$(cat)

CWD_VAL=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
[ -z "$CWD_VAL" ] && CWD_VAL=$(pwd)
HOME_DIR="$HOME"
CWD_DISPLAY="${CWD_VAL/#$HOME_DIR/\~}"
ESC=$'\033'
COLS=${COLUMNS:-$(tput cols 2>/dev/null || echo 120)}
THRESHOLD=$(( COLS * 95 / 100 ))

repeat_char() {
  local c="$1" n="$2" s=""
  for ((i=0; i<n; i++)); do s+="$c"; done
  printf '%s' "$s"
}

make_bar() {
  local pct="${1%.*}"
  [ -z "$pct" ] && pct=0
  (( pct < 0 )) && pct=0
  (( pct > 100 )) && pct=100
  local filled=$(( pct * 15 / 100 ))
  local empty=$(( 15 - filled ))
  local color
  if (( pct >= 80 )); then color="31"
  elif (( pct >= 50 )); then color="33"
  else color="32"
  fi
  printf '%s%s%s%s%s %d%%' \
    "${ESC}[${color}m" "$(repeat_char '█' $filled)" \
    "${ESC}[90m" "$(repeat_char '░' $empty)" \
    "${ESC}[0m" "$pct"
}

# Two logical groups for clean wrapping:
# Group 1 (Status): Model, Elapsed, Cost, Lines, Context Bar, Rate limits
# Group 2 (Environment): CWD, Git repo/branch, Worktree, PR, Vim, Agent, Output style, Version
segs_status=()
segs_env=()

add_status_seg() {
  local vlen="$1"; shift
  segs_status+=("${vlen}:$*")
}

add_env_seg() {
  local vlen="$1"; shift
  segs_env+=("${vlen}:$*")
}

# Model + Effort + Think (combined segment)
model=$(echo "$input" | jq -r '.model.display_name // empty')
effort=$(echo "$input" | jq -r '.effort.level // empty')
thinking_on=$(echo "$input" | jq -r '.thinking.enabled // false')
if [ -n "$model" ]; then
  model_str="${ESC}[1;37m${model}${ESC}[0m"
  model_vlen=${#model}
  if [ -n "$effort" ]; then
    model_str+="${ESC}[2m/${effort}${ESC}[0m"
    model_vlen=$(( model_vlen + 1 + ${#effort} ))
  fi
  if [ "$thinking_on" = "true" ]; then
    model_str+="${ESC}[2;36m 💭${ESC}[0m"
    model_vlen=$(( model_vlen + 3 ))
  fi
  add_status_seg $model_vlen "$model_str"
fi

# Metrics: Turn duration & Real Output TPS
metrics_json=$(python3 -c '
import sys, os, json

def compute():
    try:
        inp = json.load(sys.stdin)
    except Exception:
        return "{}"

    session_id = inp.get("session_id", "default")
    transcript_path = inp.get("transcript_path", "")
    total_dur_ms = inp.get("cost", {}).get("total_duration_ms", 0)
    api_ms = inp.get("cost", {}).get("total_api_duration_ms", 0)

    unique_msgs = {}
    if transcript_path and os.path.isfile(transcript_path):
        try:
            with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "\"output_tokens\":" in line:
                        try:
                            d = json.loads(line)
                            msg = d.get("message", {})
                            mid = msg.get("id")
                            u = msg.get("usage", {})
                            if mid and "output_tokens" in u:
                                unique_msgs[mid] = u["output_tokens"]
                        except:
                            pass
        except:
            pass

    cw = inp.get("context_window", {})
    total_out = sum(unique_msgs.values()) if unique_msgs else (cw.get("total_output_tokens", 0) or cw.get("current_usage", {}).get("output_tokens", 0))

    cache_file = f"/tmp/.claude_metrics_{session_id}.json"
    cached = {}
    if os.path.isfile(cache_file):
        try:
            with open(cache_file, "r") as f:
                cached = json.load(f)
        except:
            pass

    prev_api_ms = cached.get("api_ms", 0)
    prev_out = cached.get("out_tokens", 0)
    prev_tps = cached.get("tps", 0.0)
    prev_total_dur = cached.get("total_dur_ms", 0)

    delta_api_ms = api_ms - prev_api_ms
    delta_out = total_out - prev_out

    if delta_api_ms >= 500 and delta_out > 0:
        tps = (delta_out * 1000.0) / delta_api_ms
    elif prev_tps > 0:
        tps = prev_tps
    elif api_ms > 0 and total_out > 0:
        tps = (total_out * 1000.0) / api_ms
    else:
        tps = 0.0

    delta_dur_ms = total_dur_ms - prev_total_dur if (prev_total_dur > 0 and total_dur_ms >= prev_total_dur) else total_dur_ms
    if delta_dur_ms <= 0:
        delta_dur_ms = total_dur_ms

    cached_data = {
        "api_ms": api_ms,
        "out_tokens": total_out,
        "tps": round(tps, 1),
        "total_dur_ms": total_dur_ms
    }
    try:
        with open(cache_file, "w") as f:
            json.dump(cached_data, f)
    except:
        pass

    return json.dumps({
        "tps": round(tps, 1) if tps > 0 else 0.0,
        "turn_dur_s": int(round(delta_dur_ms / 1000.0)),
        "total_dur_s": int(round(total_dur_ms / 1000.0))
    })

sys.stdout.write(compute())
' <<< "$input" 2>/dev/null)

if [ -n "$metrics_json" ]; then
  dur_s=$(echo "$metrics_json" | jq -r '.turn_dur_s // 0' 2>/dev/null || echo 0)
  tps=$(echo "$metrics_json" | jq -r '.tps // 0' 2>/dev/null || echo 0)

  if (( dur_s > 0 )); then
    if (( dur_s < 60 )); then
      elapsed_str="⏳${dur_s}s"
    elif (( dur_s < 3600 )); then
      elapsed_str="⏳$(( dur_s / 60 ))m$(printf '%02d' $(( dur_s % 60 )))s"
    else
      elapsed_str="⏳$(( dur_s / 3600 ))h$(printf '%02d' $(( dur_s % 3600 / 60 )))m"
    fi
    add_status_seg ${#elapsed_str} "${ESC}[36m${elapsed_str}${ESC}[0m"
  fi

  if [ -n "$tps" ] && [ "$tps" != "0" ] && [ "$tps" != "0.0" ]; then
    tps_str="⚡${tps}t/s"
    add_status_seg ${#tps_str} "${ESC}[2;33m${tps_str}${ESC}[0m"
  fi
fi

# Lines changed
lines_add=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
lines_rm=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
if [ "${lines_add:-0}" -gt 0 ] 2>/dev/null || [ "${lines_rm:-0}" -gt 0 ] 2>/dev/null; then
  lines_str="+${lines_add}/-${lines_rm}"
  add_status_seg ${#lines_str} "${ESC}[32m+${lines_add}${ESC}[2m/${ESC}[31m-${lines_rm}${ESC}[0m"
fi

# Context window: bar is always 20 chars + " NN%"
ctx_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
if [ -n "$ctx_pct" ]; then
  ctx_bar=$(make_bar "$ctx_pct")
  ctx_pct_int="${ctx_pct%.*}"; [ -z "$ctx_pct_int" ] && ctx_pct_int=0
  pct_digits=${#ctx_pct_int}
  ctx_vlen=$(( 4 + 15 + 1 + pct_digits + 1 ))  # "Ctx " + bar_chars + " " + digits + "%"
  ctx_tokens=$(echo "$input" | jq -r '
    .context_window as $cw |
    if $cw == null then empty else
      # 1. 计算 current_usage 真实总和（含缓存写入与读取）
      ($cw.current_usage // {}) as $u |
      (($u.input_tokens // 0) + ($u.output_tokens // 0) + ($u.cache_creation_input_tokens // 0) + ($u.cache_read_input_tokens // 0)) as $from_usage |
      # 2. 从 total_input + total_output 获取
      (($cw.total_input_tokens // 0) + ($cw.total_output_tokens // 0)) as $from_totals |
      # 3. 从 context_window_size * used_percentage 计算基准用量（防止缓存 token 未合并导致虚低）
      (if ($cw.context_window_size // 0) > 0 and ($cw.used_percentage // 0) > 0 then
        ($cw.context_window_size * $cw.used_percentage / 100 | round)
       else 0 end) as $from_pct |
      # 取最合理的最大真实 Token 值
      ([$from_usage, $from_totals, $from_pct] | max) as $total |
      if $total <= 0 then empty
      elif $total >= 1000000 then (($total / 100000 | round) / 10 | tostring) + "M"
      elif $total >= 10000 then (($total + 500) / 1000 | floor | tostring) + "k"
      elif $total >= 1000 then (($total / 100 | round) / 10 | tostring) + "k"
      else ($total | tostring) end
    end
  ')
  ctx_str="${ESC}[90mCtx ${ESC}[0m${ctx_bar}"
  if [ -n "$ctx_tokens" ]; then
    ctx_str+=" ${ESC}[90m(${ctx_tokens})${ESC}[0m"
    ctx_vlen=$(( ctx_vlen + 2 + ${#ctx_tokens} + 1 ))  # " (" + tokens + ")"
  fi
  add_status_seg $ctx_vlen "$ctx_str"
fi

# Rate limits 5h
rl5=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
if [ -n "$rl5" ]; then
  rl5_int="${rl5%.*}"; [ -z "$rl5_int" ] && rl5_int=0
  (( rl5_int < 0 )) && rl5_int=0; (( rl5_int > 100 )) && rl5_int=100
  rl5_vlen=$(( 3 + 15 + 1 + ${#rl5_int} + 1 ))  # "5h " + bar + " " + digits + "%"
  add_status_seg $rl5_vlen "${ESC}[90m5h ${ESC}[0m$(make_bar "$rl5")"
fi

# Rate limits 7d
rl7=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
if [ -n "$rl7" ]; then
  rl7_int="${rl7%.*}"; [ -z "$rl7_int" ] && rl7_int=0
  (( rl7_int < 0 )) && rl7_int=0; (( rl7_int > 100 )) && rl7_int=100
  rl7_vlen=$(( 3 + 15 + 1 + ${#rl7_int} + 1 ))
  add_status_seg $rl7_vlen "${ESC}[90m7d ${ESC}[0m$(make_bar "$rl7")"
fi

# Repo + git branch
repo=$(echo "$input" | jq -r 'if .workspace.repo != null then .workspace.repo.owner + "/" + .workspace.repo.name else empty end')
if [ -n "$repo" ]; then
  branch=$(git -C "$CWD_VAL" branch --show-current 2>/dev/null || true)
  repo_str="$repo"
  [ -n "$branch" ] && repo_str="${repo}:${branch}"
  add_env_seg ${#repo_str} "${ESC}[2;36m${repo_str}${ESC}[0m"
fi

# Worktree
wt=$(echo "$input" | jq -r 'if .worktree.name != null or .workspace.git_worktree != null then (if .worktree.name != null then .worktree.name else "" end) + (if .workspace.git_worktree != null then "(" + .workspace.git_worktree + ")" else "" end) + (if .worktree.branch != null then "@" + .worktree.branch else "" end) else empty end')
[ -n "$wt" ] && add_env_seg ${#wt} "${ESC}[33m${wt}${ESC}[0m"

# PR
pr=$(echo "$input" | jq -r 'if .pr.number != null then "PR #" + (.pr.number | tostring) + " " + (.pr.review_state // "open") else empty end')
[ -n "$pr" ] && add_env_seg ${#pr} "${ESC}[32m${pr}${ESC}[0m"

# Vim
vim_mode=$(echo "$input" | jq -r '.vim.mode // empty')
if [ -n "$vim_mode" ]; then
  case "$vim_mode" in
    NORMAL) vim_color="1;32" ;;
    INSERT) vim_color="1;34" ;;
    VISUAL*) vim_color="1;35" ;;
    *) vim_color="1;37" ;;
  esac
  vim_str="VIM:${vim_mode}"
  add_env_seg ${#vim_str} "${ESC}[${vim_color}m${vim_str}${ESC}[0m"
fi

# Agent
agent=$(echo "$input" | jq -r 'if .agent.name != null and .agent.name != "claude" then .agent.name + (if .agent.type != null then " (" + .agent.type + ")" else "" end) else empty end')
[ -n "$agent" ] && add_env_seg ${#agent} "${ESC}[1;36m${agent}${ESC}[0m"

# Output style
output_style=$(echo "$input" | jq -r 'if .output_style.name != null and .output_style.name != "" and (.output_style.name | ascii_downcase) != "default" then .output_style.name else empty end')
if [ -n "$output_style" ]; then
  style_str="[${output_style}]"
  add_env_seg ${#style_str} "${ESC}[2;36m${style_str}${ESC}[0m"
fi

# Formatting and Layout
SEP=" ${ESC}[90m│${ESC}[0m "

render_group() {
  local -n arr=$1
  local out=""
  local first=1
  for entry in "${arr[@]}"; do
    local seg="${entry#*:}"
    if (( first )); then
      out="$seg"
      first=0
    else
      out+="${SEP}${seg}"
    fi
  done
  printf '%s' "$out"
}

# Single Line Output:
str_status="$(render_group segs_status)"
str_env="$(render_group segs_env)"

if [ -n "$str_status" ] && [ -n "$str_env" ]; then
  printf '%s%s%s\n' "$str_status" "$SEP" "$str_env"
elif [ -n "$str_status" ]; then
  printf '%s\n' "$str_status"
else
  printf '%s\n' "$str_env"
fi
