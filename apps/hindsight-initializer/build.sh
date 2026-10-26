#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
GO="${GO:-go}"
OUT="${OUT:-../../output/hindsight-initializer}"
mkdir -p "$OUT"
"$GO" mod verify
"$GO" test ./...
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 "$GO" build -trimpath -ldflags '-s -w -H=windowsgui' -o "$OUT/Hindsight-Setup-windows-x64.exe" .
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 "$GO" build -trimpath -ldflags '-s -w' -o "$OUT/hindsight-setup-linux-x64" .
cp README.md "$OUT/README.md"
cp Hindsight-Setup-Web.cmd "$OUT/Hindsight-Setup-Web.cmd"
cp -R licenses "$OUT/"
