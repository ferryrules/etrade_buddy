#!/usr/bin/env bash
# Bounce the LaunchAgent. Use this after editing config.ini or pulling new code.
set -u

PLIST_NAME="com.ferryrules.etrade-voice-assistant"
PLIST_FILE="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

if [[ ! -f "$PLIST_FILE" ]]; then
    echo "  [!] LaunchAgent not installed. Run ./install.sh first."
    exit 1
fi

launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"
echo "  [ok] Restarted. Run ./status.sh to confirm it's up."
