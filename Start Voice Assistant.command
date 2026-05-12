#!/bin/bash
# =====================================================
# Double-click this file to start Grandpop's
# E*TRADE Voice Assistant.
# =====================================================

cd "$(dirname "$0")"

# --- Auto-update (silent, never blocks startup) ---
if [ -d ".git" ] && command -v git &>/dev/null; then
    echo "  Checking for updates..."
    if timeout 10 git pull --ff-only origin main &>/dev/null 2>&1; then
        echo "  [OK] Up to date."
    else
        echo "  [OK] Couldn't check for updates. No problem, continuing."
    fi
    # Reinstall dependencies in case requirements changed
    if [ -f ".venv/bin/pip" ]; then
        .venv/bin/pip install -r requirements.txt --quiet 2>/dev/null
    fi
fi

# Check if setup has been run
if [ ! -d ".venv" ]; then
    echo ""
    echo "  It looks like the setup hasn't been run yet!"
    echo "  Please double-click 'Setup Voice Assistant' first."
    echo ""
    read -r -p "  Press Return to close..."
    exit 1
fi

# Check if start.sh exists (created by setup)
if [ -f "start.sh" ]; then
    echo ""
    echo "  Starting Grandpop's E*TRADE Voice Assistant..."
    echo ""
    ./start.sh
else
    # Fallback: run directly with defaults
    echo ""
    echo "  Starting Grandpop's E*TRADE Voice Assistant..."
    echo ""
    source .venv/bin/activate
    cd etrade_python_client
    python3 -u voice_assistant.py --button space
fi

echo ""
echo ""
echo "  =================================================="
echo "  The voice assistant has stopped."
echo "  You can close this window now."
echo "  =================================================="
echo ""
read -r -p "  Press Return to close..."
