#!/bin/bash
# Uninstaller for AI Document Assistant (macOS)
# Double-click this file (or run it in Terminal) to remove the app and its
# saved settings/history from this Mac.

set -e

APP_NAME="AI Document Assistant.app"
APP_PATH="/Applications/${APP_NAME}"
SUPPORT_DIR="${HOME}/Library/Application Support/AI_Document_Assistant"

echo "==================================================="
echo " Uninstall AI Document Assistant"
echo "==================================================="
echo ""
echo "This will remove:"
echo "  - ${APP_PATH}"
echo "  - ${SUPPORT_DIR} (saved settings / API key / history)"
echo ""
read -p "Continue? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Cancelled."
  exit 0
fi

if [ -d "$APP_PATH" ]; then
  echo "Removing application..."
  rm -rf "$APP_PATH"
else
  echo "Application not found at $APP_PATH (may already be removed)."
fi

if [ -d "$SUPPORT_DIR" ]; then
  read -p "Also delete saved settings/history at ${SUPPORT_DIR}? [y/N] " del_data
  if [[ "$del_data" == "y" || "$del_data" == "Y" ]]; then
    rm -rf "$SUPPORT_DIR"
    echo "Settings/history removed."
  fi
fi

echo ""
echo "Uninstall complete."
read -p "Press Enter to close..."
