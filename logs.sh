#!/usr/bin/env bash
# Live-tail the most recent session log. Ctrl-C to stop.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/etrade_python_client/logs"

LATEST=$(ls -t "$LOG_DIR"/session_*.log 2>/dev/null | head -1)
if [[ -z "$LATEST" ]]; then
    echo "  [!] No session logs found in $LOG_DIR yet."
    echo "      The assistant probably hasn't run. Try ./status.sh."
    # Fall back to the LaunchAgent's own stdout/stderr
    if [[ -f "$LOG_DIR/launchagent.log" ]]; then
        echo
        echo "  Showing $LOG_DIR/launchagent.log instead:"
        echo
        exec tail -f "$LOG_DIR/launchagent.log"
    fi
    exit 1
fi

echo "  Tailing $LATEST  (Ctrl-C to stop)"
echo
exec tail -f "$LATEST"
