#!/usr/bin/env bash
# Show whether the voice assistant is running, and the last few log lines.
set -u

PLIST_NAME="com.ferryrules.etrade-voice-assistant"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/etrade_python_client/logs"

LINE=$(launchctl list 2>/dev/null | awk -v n="$PLIST_NAME" '$3 == n')
if [[ -z "$LINE" ]]; then
    echo "  [!] LaunchAgent not loaded. Run ./install.sh or ./restart.sh."
    exit 1
fi

PID=$(awk '{print $1}' <<<"$LINE")
LAST_EXIT=$(awk '{print $2}' <<<"$LINE")

if [[ "$PID" == "-" ]]; then
    echo "  [!] Not running. Last exit code: $LAST_EXIT"
    echo "      Run ./logs.sh to see why, then ./restart.sh."
else
    echo "  [ok] Running. PID $PID"
    ps -p "$PID" -o pid,etime,command 2>/dev/null | tail -n +2 | sed 's/^/       /'
fi

echo
LATEST=$(ls -t "$LOG_DIR"/session_*.log 2>/dev/null | head -1)
if [[ -n "$LATEST" ]]; then
    echo "  Last 10 lines of $(basename "$LATEST"):"
    tail -10 "$LATEST" | sed 's/^/    /'
else
    echo "  No session logs yet."
fi
