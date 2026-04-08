#!/usr/bin/env bash
set -euo pipefail

APP_NAME="imarisha-scan"
ENTRYPOINT="src/imarisha_scan/main.py"
DIST_DIR="dist/macos"
PYI_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$PWD/.pyinstaller}"

mkdir -p "$DIST_DIR"
mkdir -p "$PYI_CONFIG_DIR"

# Keep pyinstaller cache local to project to avoid stale/corrupt global cache issues.
export PYINSTALLER_CONFIG_DIR="$PYI_CONFIG_DIR"

# macOS build must run on macOS host.
pyinstaller \
  --clean \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  "$ENTRYPOINT"

echo "Built $DIST_DIR/$APP_NAME.app"
