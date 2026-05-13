#!/usr/bin/env bash
# Remove the LaunchAgent so the assistant no longer auto-starts at login.
# Project files and the venv are left alone — to fully wipe, just delete this folder.
set -u

PLIST_NAME="com.ferryrules.etrade-voice-assistant"
PLIST_FILE="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

if [[ -f "$PLIST_FILE" ]]; then
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    rm -f "$PLIST_FILE"
    echo "  [ok] LaunchAgent removed. The assistant will no longer auto-start."
else
    echo "  [ok] No LaunchAgent installed (nothing to do)."
fi

echo
echo "  The cached E*TRADE OAuth token is still in your Keychain."
echo "  To remove it too:"
echo "    .venv/bin/python etrade_python_client/voice_assistant.py --forget-auth"
