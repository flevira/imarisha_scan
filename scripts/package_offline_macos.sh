#!/usr/bin/env bash
set -euo pipefail

APP_NAME="imarisha-scan"
ENTRYPOINT="src/imarisha_scan/main.py"
DIST_DIR="dist/macos"

mkdir -p "$DIST_DIR"

if ! command -v flet >/dev/null 2>&1; then
  echo "Missing 'flet' CLI. Install UI extras first:"
  echo "  python -m pip install .[ui]"
  exit 1
fi

# Build macOS app via Flet CLI (avoids PyInstaller framework signing failures on some macOS/Python combos).
flet build macos "$ENTRYPOINT" \
  --output "$DIST_DIR" \
  --project "$APP_NAME" \
  --product "Imarisha Scan"

APP_CANDIDATE="$(find "$DIST_DIR" -maxdepth 2 -type d -name '*.app' | head -n 1 || true)"
if [ -z "$APP_CANDIDATE" ]; then
  echo "Build finished but no .app bundle found under $DIST_DIR"
  exit 1
fi

if [ "$APP_CANDIDATE" != "$DIST_DIR/$APP_NAME.app" ]; then
  rm -rf "$DIST_DIR/$APP_NAME.app"
  mv "$APP_CANDIDATE" "$DIST_DIR/$APP_NAME.app"
fi

echo "Built $DIST_DIR/$APP_NAME.app"
