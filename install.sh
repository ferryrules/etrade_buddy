#!/usr/bin/env bash
# =============================================================================
# E*TRADE Voice Assistant — installer
#
# One command, run once:
#
#     ./install.sh
#
# What it does:
#   1. Installs Homebrew + portaudio if missing
#   2. Creates the Python virtualenv and installs requirements
#   3. Creates etrade_python_client/config.ini from the template
#      and prompts you for your E*TRADE consumer key + secret
#   4. Installs a macOS LaunchAgent that:
#        - Auto-starts the assistant every time grandpa logs in
#        - Auto-restarts it if it crashes (after a 30s cool-down)
#        - Runs it as a pure background process — no Terminal window
#
# After this, grandpa never has to click anything. He just logs in,
# hears "Welcome to your E-Trade voice assistant", and presses the pedal.
#
# Maintenance (for you, not grandpa):
#   ./status.sh       - is it running?
#   ./logs.sh         - tail the latest session log
#   ./restart.sh      - bounce the LaunchAgent
#   ./uninstall.sh    - remove auto-start (project files untouched)
#   ./setup_pedal.sh  - optional: detect foot pedal + remap to F13
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
CONFIG_FILE="$SCRIPT_DIR/etrade_python_client/config.ini"
CONFIG_TEMPLATE="$SCRIPT_DIR/etrade_python_client/config.example.ini"
LOG_DIR="$SCRIPT_DIR/etrade_python_client/logs"
PLIST_NAME="com.ferryrules.etrade-voice-assistant"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/$PLIST_NAME.plist"

# Default trigger key. If you have a foot pedal that sends F13, this is right.
# If you have a different pedal, run ./setup_pedal.sh after install to remap.
BUTTON_KEY="${BUTTON_KEY:-f13}"
FALLBACK_KEY="${FALLBACK_KEY:-shift}"
ALERT_EMAIL="${ALERT_EMAIL:-ferris@ferryrules.com}"

step() { echo; echo "==> $*"; }
ok()   { echo "    [ok] $*"; }
warn() { echo "    [!]  $*"; }

# Strip Gatekeeper quarantine so macOS doesn't block our scripts/files
xattr -cr "$SCRIPT_DIR" 2>/dev/null || true

# -----------------------------------------------------------------------------
step "1/5 Homebrew + portaudio (mic support)"
# -----------------------------------------------------------------------------
if command -v brew &>/dev/null; then
    ok "Homebrew already installed"
else
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [[ -x /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        # Make Homebrew available in future shells
        if ! grep -q '/opt/homebrew/bin/brew shellenv' "$HOME/.zprofile" 2>/dev/null; then
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
        fi
    fi
    ok "Homebrew installed"
fi

if brew list portaudio &>/dev/null; then
    ok "portaudio already installed"
else
    brew install portaudio
    ok "portaudio installed"
fi

# -----------------------------------------------------------------------------
step "2/5 Python virtual environment + dependencies"
# -----------------------------------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
    ok "Created venv at $VENV_DIR"
else
    ok "venv already exists"
fi

"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --quiet
ok "Dependencies installed"

# -----------------------------------------------------------------------------
step "3/5 E*TRADE API keys"
# -----------------------------------------------------------------------------
if [[ ! -f "$CONFIG_FILE" ]]; then
    cp "$CONFIG_TEMPLATE" "$CONFIG_FILE"
    ok "Created $CONFIG_FILE from template"
fi

if grep -q "PLEASE_ENTER" "$CONFIG_FILE"; then
    echo
    echo "    Get your keys from: https://developer.etrade.com"
    echo "    Leave blank and press Return to skip (you can edit the file later)."
    echo
    read -rp "    Consumer Key:    " USER_KEY
    read -rp "    Consumer Secret: " USER_SECRET
    if [[ -n "$USER_KEY" && -n "$USER_SECRET" ]]; then
        # Use Python so we don't have to fight sed escaping
        "$VENV_DIR/bin/python" -c "
import sys
content = open('$CONFIG_FILE').read()
content = content.replace('PLEASE_ENTER_CONSUMER_KEY_HERE', sys.argv[1])
content = content.replace('PLEASE_ENTER_CONSUMER_SECRET_HERE', sys.argv[2])
open('$CONFIG_FILE', 'w').write(content)
" "$USER_KEY" "$USER_SECRET"
        ok "Saved API keys to $CONFIG_FILE"
    else
        warn "Skipped. Edit $CONFIG_FILE later with your real keys."
    fi
else
    ok "API keys already configured"
fi

# -----------------------------------------------------------------------------
step "4/5 macOS + Chrome permissions reminder"
# -----------------------------------------------------------------------------
cat <<EOF
    The first time the assistant runs, macOS will need TWO permissions.
    The popups appear at login. If you miss them, grant manually in:
      System Settings -> Privacy & Security

      1. MICROPHONE       - so it can hear grandpa's voice
      2. INPUT MONITORING - so it can detect the foot pedal

    Both should be granted to:  $VENV_DIR/bin/python

    THIRD permission (in Chrome itself) so the assistant can read the
    OAuth verification code off the page automatically:

      Chrome menu bar -> View -> Developer
                       -> Allow JavaScript from Apple Events  [ON]

    Without this, you'll fall back to reading the verification code aloud
    once a day. The assistant will tell you if it's missing.

EOF

# -----------------------------------------------------------------------------
step "5/5 Background launcher (LaunchAgent)"
# -----------------------------------------------------------------------------
mkdir -p "$PLIST_DIR" "$LOG_DIR"

cat > "$PLIST_FILE" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${VENV_DIR}/bin/python</string>
        <string>-u</string>
        <string>${SCRIPT_DIR}/etrade_python_client/voice_assistant.py</string>
        <string>--button</string>
        <string>${BUTTON_KEY}</string>
        <string>--fallback-button</string>
        <string>${FALLBACK_KEY}</string>
        <string>--alert-email</string>
        <string>${ALERT_EMAIL}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}/etrade_python_client</string>

    <!-- Start at login -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Auto-restart on crash, but don't loop on a clean exit (e.g. user quit) -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>

    <!-- Wait 30s between restarts so we don't hammer E*TRADE if something is wrong -->
    <key>ThrottleInterval</key>
    <integer>30</integer>

    <!-- Force UTF-8 so we never repeat the 'ascii codec' bug on launch -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>LANG</key>
        <string>en_US.UTF-8</string>
        <key>LC_ALL</key>
        <string>en_US.UTF-8</string>
        <key>PYTHONIOENCODING</key>
        <string>utf-8</string>
    </dict>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/launchagent.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/launchagent.log</string>
</dict>
</plist>
PLIST_EOF

# Reload (unload may fail if it wasn't loaded; that's fine)
launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"
ok "LaunchAgent installed and started"

# -----------------------------------------------------------------------------
echo
echo "============================================================"
echo "  Done. Grandpa never has to click anything to start it."
echo "============================================================"
echo
echo "  To check on it:           ./status.sh"
echo "  To watch live logs:       ./logs.sh"
echo "  To restart:               ./restart.sh"
echo "  To remove auto-start:     ./uninstall.sh"
echo "  Foot pedal not F13?       ./setup_pedal.sh"
echo
echo "  In ~10 seconds you should hear 'Welcome to your E-Trade voice assistant.'"
echo "  If you don't, run ./logs.sh to see what happened."
echo
