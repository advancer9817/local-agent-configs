#!/usr/bin/env bash
set -euo pipefail

TARGET="${HERMES_HOME:-$HOME/.hermes}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cat <<MSG
This will copy sanitized Hermes config/profile/memory files from:
  $SOURCE_DIR
to:
  $TARGET

It will NOT copy .env.example into .env automatically.
Press Ctrl-C to cancel, or Enter to continue.
MSG
read -r _

mkdir -p "$TARGET"
for path in config.yaml SOUL.md; do
  if [ -f "$SOURCE_DIR/$path" ]; then
    install -m 600 "$SOURCE_DIR/$path" "$TARGET/$path"
  fi
done

if [ -d "$SOURCE_DIR/memories" ]; then
  mkdir -p "$TARGET/memories"
  cp -f "$SOURCE_DIR"/memories/*.md "$TARGET/memories/" 2>/dev/null || true
fi

if [ -d "$SOURCE_DIR/profiles" ]; then
  mkdir -p "$TARGET/profiles"
  cp -R "$SOURCE_DIR/profiles/." "$TARGET/profiles/"
fi

echo "Restore complete. Review $SOURCE_DIR/.env.example and manually populate $TARGET/.env if needed."
echo "Run: hermes profile list && hermes config check"
