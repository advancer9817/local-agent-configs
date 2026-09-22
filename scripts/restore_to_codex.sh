#!/usr/bin/env bash
# ==============================================================================
# restore_to_codex.sh
# 将本仓库受控的 Codex 配置恢复到 ~/.codex/
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
CODEX_SRC="$REPO_DIR/codex"
TARGET_DIR="${HOME}/.codex"

echo "=== 开始恢复 Codex 配置到 ${TARGET_DIR} ==="

mkdir -p "${TARGET_DIR}"

# 1. 恢复配置
cp "${CODEX_SRC}/config.toml" "${TARGET_DIR}/config.toml"
cp "${CODEX_SRC}/instructions.md" "${TARGET_DIR}/instructions.md"
cp "${CODEX_SRC}/hooks.json" "${TARGET_DIR}/hooks.json"

echo "=== Codex 配置恢复成功（注意：敏感 Token 需在本地补充配置）==="
