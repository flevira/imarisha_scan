#!/usr/bin/env bash
set -euo pipefail

APP_NAME="imarisha-scan"
ENTRYPOINT="src/imarisha_scan/main.py"
DIST_DIR="dist/windows"

mkdir -p "$DIST_DIR"

# Windows build via pyinstaller from a Windows build host.
pyinstaller \
  --noconfirm \
  --onefile \
  --windowed \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  "$ENTRYPOINT"

echo "Built $DIST_DIR/$APP_NAME(.exe on Windows)"
