#!/bin/bash
# Build a macOS .app bundle (via PyInstaller) and package it into a
# double-clickable .dmg installer with a drag-to-Applications shortcut
# and a bundled uninstaller script.
#
# Must be run ON macOS (PyInstaller cannot cross-compile).
#
# Usage:
#   bash installer/mac/build_dmg.sh

set -e

APP_NAME="AI Document Assistant"
BIN_NAME="AI_Document_Assistant"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
STAGING_DIR="${ROOT_DIR}/dist_dmg_staging"
DMG_OUT="${ROOT_DIR}/dist_installer"
DMG_PATH="${DMG_OUT}/${BIN_NAME}_macOS.dmg"

cd "$ROOT_DIR"

echo "==> Installing dependencies"
pip install -r requirements.txt

echo "==> Building .app with PyInstaller"
pyinstaller --noconfirm --windowed \
  --name "${BIN_NAME}" \
  --add-data "web:web" \
  --add-data "fonts:fonts" \
  --collect-all webview \
  app.py

APP_BUNDLE="${DIST_DIR}/${BIN_NAME}.app"
if [ ! -d "$APP_BUNDLE" ]; then
  echo "ERROR: expected app bundle not found at ${APP_BUNDLE}"
  exit 1
fi

echo "==> Preparing DMG staging folder"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
mkdir -p "$DMG_OUT"

# Rename the bundle to the human-friendly display name inside the DMG.
cp -R "$APP_BUNDLE" "${STAGING_DIR}/${APP_NAME}.app"

# Drag-to-Applications convenience shortcut.
ln -s /Applications "${STAGING_DIR}/Applications"

# Bundle the uninstaller script alongside the app.
cp "${ROOT_DIR}/installer/mac/Uninstall AI Document Assistant.command" "${STAGING_DIR}/"
chmod +x "${STAGING_DIR}/Uninstall AI Document Assistant.command"

echo "==> Creating DMG"
rm -f "$DMG_PATH"
hdiutil create -volname "${APP_NAME}" \
  -srcfolder "$STAGING_DIR" \
  -ov -format UDZO \
  "$DMG_PATH"

echo ""
echo "Done: ${DMG_PATH}"
