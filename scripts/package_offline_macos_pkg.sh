#!/usr/bin/env bash
set -euo pipefail

APP_NAME="imarisha-scan"
APP_BUNDLE="dist/macos/${APP_NAME}.app"
PKG_OUT="dist/macos/${APP_NAME}.pkg"
IDENTIFIER="com.imarisha.scan"
VERSION="0.1.0"

if [ ! -d "$APP_BUNDLE" ]; then
  echo "Missing app bundle: $APP_BUNDLE"
  echo "Run ./scripts/package_offline_macos.sh first."
  exit 1
fi

pkgbuild \
  --component "$APP_BUNDLE" \
  --install-location "/Applications" \
  --identifier "$IDENTIFIER" \
  --version "$VERSION" \
  "$PKG_OUT"

echo "Built $PKG_OUT"
