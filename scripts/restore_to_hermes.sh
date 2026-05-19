#!/usr/bin/env bash
set -euo pipefail
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
BACKUP_DIR="$HERMES_HOME/backups/restore_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
for item in config.yaml SOUL.md memories profiles; do
  if [ -e "$HERMES_HOME/$item" ]; then cp -a "$HERMES_HOME/$item" "$BACKUP_DIR/"; fi
done
mkdir -p "$HERMES_HOME"
cp -a "$SRC_DIR/config.yaml" "$HERMES_HOME/config.yaml"
cp -a "$SRC_DIR/SOUL.md" "$HERMES_HOME/SOUL.md"
[ -d "$SRC_DIR/memories" ] && cp -a "$SRC_DIR/memories" "$HERMES_HOME/"
[ -d "$SRC_DIR/profiles" ] && cp -a "$SRC_DIR/profiles" "$HERMES_HOME/"
echo "Restored sanitized Hermes configs to $HERMES_HOME"
echo "Backup saved to $BACKUP_DIR"
echo "NOTE: .env/auth.json are intentionally not restored. Configure secrets separately."
