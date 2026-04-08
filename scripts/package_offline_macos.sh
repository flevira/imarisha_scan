#!/usr/bin/env bash
set -euo pipefail

APP_NAME="imarisha-scan"
ENTRYPOINT="src/imarisha_scan/main.py"
DIST_DIR="dist/macos"

mkdir -p "$DIST_DIR"

# macOS build must run on macOS host.
pyinstaller \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  "$ENTRYPOINT"

echo "Built $DIST_DIR/$APP_NAME.app"
