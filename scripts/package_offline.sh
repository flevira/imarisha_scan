#!/usr/bin/env bash
set -euo pipefail

APP_NAME="imarisha-scan"
ENTRYPOINT="src/imarisha_scan/main.py"

pyinstaller --noconfirm --onefile --name "$APP_NAME" "$ENTRYPOINT"

echo "Built dist/$APP_NAME"
