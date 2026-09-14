#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 安装 cc-switch 的 WSLg 输入法 (IME) 兼容修复
#
# 背景
#   上游 farion1231/cc-switch issue #7059 / #349 / #3897:
#   WebKitGTK 2.40+ 在 Linux 下, 若 GTK 探测到 fcitx5/ibus 的 IM 模块
#   而对应守护进程并未运行, 点击输入框会让 WebKitWebProcess 挂死。
#   表现为: "输入框选不了、字打不进去, 随后任何按钮都无效,
#            点返回按钮还会弹出官网网页"。
#
# 修复
#   强制 GTK 退回内置的简单输入上下文, 绕开 IME 组合态路径。
#
# 关键点 (否则修复会静默失效)
#   /etc/environment 的 PATH 通常不含 ~/.local/bin, 因此桌面项/开始菜单项
#   (Exec=cc-switch) 会直接命中 /usr/bin/cc-switch, 绕过 ~/.local/bin 里的包装脚本。
#   本脚本同时写入用户级桌面项覆盖 (~/.local/share/applications/),
#   与系统 /usr/share/applications/ 同名者优先生效, 无需 sudo。
#
# 用法
#   ./install.sh                      # 安装到当前用户
#   BIN_DIR=/somewhere ./install.sh   # 自定义安装位置
#   ./install.sh --check              # 仅做环境自检, 不改动任何文件
# ---------------------------------------------------------------------------
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BIN_DIR="${BIN_DIR:-${XDG_BIN_HOME:-$HOME/.local/bin}}"
APP_DIR="${APP_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/applications}"
APP_CMD="${APP_CMD:-cc-switch}"
APP_NAME="${APP_NAME:-CC Switch}"
DESKTOP_BASENAME="${DESKTOP_BASENAME:-$APP_NAME}"
HANDLER_BASENAME="${HANDLER_BASENAME:-cc-switch-handler}"

say() { printf '%s\n' "$*"; }
err() { printf 'ERROR: %s\n' "$*" >&2; }

# --------------------------------------------------------------------------
# 环境自检: 判定本机是否命中该缺陷的触发条件
# --------------------------------------------------------------------------
check_env() {
  local wk ver mods daemon
  wk="$(dpkg-query -W -f='${Version}' libwebkit2gtk-4.1-0 2>/dev/null || echo 'not-installed')"
  say "WebKitGTK (libwebkit2gtk-4.1-0) : $wk"

  mods="$(find /usr/lib /usr/lib64 -name 'im-fcitx*.so' -o -name 'im-ibus*.so' 2>/dev/null | head -5 || true)"
  if [ -n "$mods" ]; then
    say "已安装的 GTK IM 模块            :"; printf '%s\n' "$mods" | sed 's/^/    /'
  else
    say "已安装的 GTK IM 模块            : (未发现 fcitx/ibus 模块)"
  fi

  daemon="$(ps -eo cmd 2>/dev/null | grep -E '[f]citx|[i]bus-daemon' || true)"
  if [ -n "$daemon" ]; then
    say "运行中的输入法守护进程          : 有 (本缺陷通常不会命中)"
  else
    say "运行中的输入法守护进程          : 无"
  fi

  say
  say "命中判定: 需要 [WebKitGTK >= 2.40] 且 [IM 模块存在] 且 [守护进程未运行]。"
  say "          三者同时成立 => 点输入框会挂死 WebProcess, 建议安装本修复。"
}

# --------------------------------------------------------------------------
# 写入一个桌面项 (覆盖系统同名项)
#   $1 = 目标路径
#   $2 = 额外行 (如 NoDisplay=true), 可为空
# --------------------------------------------------------------------------
write_desktop() {
  local target="$1" extra="$2"
  cat > "$target" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=All-in-One Assistant for Claude Code, Codex & Gemini CLI
Exec=$BIN_DIR/$APP_CMD %u
Terminal=false
Icon=$APP_CMD
StartupWMClass=$APP_CMD
MimeType=x-scheme-handler/ccswitch
$extra
EOF
  chmod 644 "$target"
}

# --------------------------------------------------------------------------
# 通用桌面项 (可点击启动 + 处理 ccswitch:// 深链接)
# --------------------------------------------------------------------------
write_app_desktop() {
  cat > "$1" <<EOF
[Desktop Entry]
Categories=
Comment=All-in-One Assistant for Claude Code, Codex & Gemini CLI
Exec=$BIN_DIR/$APP_CMD %u
StartupWMClass=$APP_CMD
Icon=$APP_CMD
Name=$APP_NAME
Terminal=false
Type=Application
MimeType=x-scheme-handler/ccswitch
EOF
  chmod 644 "$1"
}

if [ "${1:-}" = "--check" ]; then
  check_env
  exit 0
fi

# --- 1. 包装脚本 -----------------------------------------------------------
say "==> 安装包装脚本: $BIN_DIR/$APP_CMD"
install -Dm755 "$SRC_DIR/cc-switch" "$BIN_DIR/$APP_CMD"

# --- 2. 桌面项覆盖 ---------------------------------------------------------
say "==> 写入用户级桌面项覆盖: $APP_DIR/"
mkdir -p "$APP_DIR"

write_app_desktop "$APP_DIR/${DESKTOP_BASENAME}.desktop"
write_desktop     "$APP_DIR/${HANDLER_BASENAME}.desktop" "NoDisplay=true"

command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database "$APP_DIR" 2>/dev/null || true

# --- 3. 提示 --------------------------------------------------------------
cat <<EOF

==> 安装完成

请重启应用使环境变量进入运行进程:
    $BIN_DIR/$APP_CMD restart

随后用以下命令确认修复真的生效 (读运行进程的真实环境, 而非脚本内容):
    PID=\$(pgrep -f "^/usr/bin/$APP_CMD" | head -1)
    tr '\\0' '\\n' < "/proc/\${PID}/environ" | grep -E "^(GTK_IM_MODULE|QT_IM_MODULE|XMODIFIERS)="

期望输出:
    GTK_IM_MODULE=gtk-im-context-simple
    QT_IM_MODULE=simple
    XMODIFIERS=@im=none

若无输出 => 应用是从某个未覆盖的入口启动的, 检查:
    $APP_DIR/  与  /usr/share/applications/  中是否有同名 .desktop 且 Exec 直呼二进制。

回滚:
    rm -f "$APP_DIR/${DESKTOP_BASENAME}.desktop" "$APP_DIR/${HANDLER_BASENAME}.desktop"
    rm -f "$BIN_DIR/$APP_CMD"
EOF
