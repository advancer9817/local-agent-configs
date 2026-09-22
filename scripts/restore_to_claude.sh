#!/usr/bin/env bash
# ==============================================================================
# restore_to_claude.sh
# 将本仓库受控的 Claude Code 配置与规则集恢复到 ~/.claude/
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
CLAUDE_SRC="$REPO_DIR/claude"
TARGET_DIR="${HOME}/.claude"

echo "=== 开始恢复 Claude Code 配置到 ${TARGET_DIR} ==="

mkdir -p "${TARGET_DIR}/rules/common"
mkdir -p "${TARGET_DIR}/rules/typescript"
mkdir -p "${TARGET_DIR}/plugins"

# 1. 恢复核心配置文件
cp "${CLAUDE_SRC}/settings.json" "${TARGET_DIR}/settings.json"
cp "${CLAUDE_SRC}/settings.local.json" "${TARGET_DIR}/settings.local.json"
cp "${CLAUDE_SRC}/config.json" "${TARGET_DIR}/config.json"
cp "${CLAUDE_SRC}/CLAUDE.md" "${TARGET_DIR}/CLAUDE.md"
cp "${CLAUDE_SRC}/scripts/statusline.sh" "${TARGET_DIR}/statusline.sh"
chmod +x "${TARGET_DIR}/statusline.sh"

# 2. 恢复插件元数据
cp "${CLAUDE_SRC}/installed_plugins.json" "${TARGET_DIR}/plugins/installed_plugins.json"
cp "${CLAUDE_SRC}/known_marketplaces.json" "${TARGET_DIR}/plugins/known_marketplaces.json"

# 3. 恢复规则系统
cp -r "${CLAUDE_SRC}/rules/common/"* "${TARGET_DIR}/rules/common/"
cp -r "${CLAUDE_SRC}/rules/typescript/"* "${TARGET_DIR}/rules/typescript/"

echo "=== Claude Code 配置恢复成功 ==="
