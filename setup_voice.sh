#!/bin/bash
# =============================================================================
# E*TRADE Voice Assistant — One-Time Setup
#
# This script installs everything needed to run Grandpop's voice assistant.
# Just open Terminal and run:
#
#     cd ~/Downloads/EtradePythonClient
#     ./setup_voice.sh
#
# It will walk you through each step and explain what's happening.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
CONFIG_FILE="$SCRIPT_DIR/etrade_python_client/config.ini"

# --- Helpers ---

print_step() {
    echo ""
    echo "============================================"
    echo "  STEP $1: $2"
    echo "============================================"
    echo ""
}

print_ok() {
    echo "  [OK] $1"
}

print_skip() {
    echo "  [ALREADY DONE] $1"
}

print_warning() {
    echo ""
    echo "  !! $1"
    echo ""
}

wait_for_enter() {
    echo ""
    echo "  Press Return to continue..."
    read -r
}

# --- Strip Gatekeeper quarantine flags so macOS doesn't block our files ---
xattr -cr "$SCRIPT_DIR" 2>/dev/null

# --- Start ---

echo ""
echo "  =================================================="
echo "  Welcome to the E*TRADE Voice Assistant Setup!"
echo "  =================================================="
echo ""
echo "  This will install everything Grandpop needs."
echo "  It takes about 10-15 minutes."
echo "  I'll explain each step as we go."
echo ""
echo "  If anything goes wrong, take a screenshot"
echo "  and send it to Ferris."
echo ""

wait_for_enter

# ==========================================================
# STEP 1: Homebrew
# ==========================================================

print_step 1 "Installing Homebrew (a tool that installs other tools)"

if command -v brew &>/dev/null; then
    print_skip "Homebrew is already installed."
else
    echo "  Homebrew is not installed yet. Installing now..."
    echo ""
    echo "  ** It might ask for your computer's password. **"
    echo "  ** When you type it, nothing will appear on    **"
    echo "  ** the screen — that's normal! Just type it    **"
    echo "  ** and press Return.                           **"
    echo ""
    echo "  This can take 5-10 minutes. Please be patient."
    echo ""

    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for Apple Silicon Macs
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        # Also add to shell profile so it persists
        SHELL_PROFILE=""
        if [ -f "$HOME/.zprofile" ]; then
            SHELL_PROFILE="$HOME/.zprofile"
        elif [ -f "$HOME/.zshrc" ]; then
            SHELL_PROFILE="$HOME/.zshrc"
        else
            SHELL_PROFILE="$HOME/.zprofile"
        fi

        if ! grep -q 'homebrew' "$SHELL_PROFILE" 2>/dev/null; then
            echo '' >> "$SHELL_PROFILE"
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$SHELL_PROFILE"
            print_ok "Added Homebrew to your shell profile."
        fi
    fi

    if command -v brew &>/dev/null; then
        print_ok "Homebrew installed successfully!"
    else
        echo ""
        echo "  ERROR: Homebrew doesn't seem to be working."
        echo "  Try closing Terminal, reopening it, and running"
        echo "  this setup script again."
        echo ""
        exit 1
    fi
fi

# ==========================================================
# STEP 2: PortAudio
# ==========================================================

print_step 2 "Installing PortAudio (lets the app use the microphone)"

if brew list portaudio &>/dev/null; then
    print_skip "PortAudio is already installed."
else
    echo "  Installing PortAudio..."
    brew install portaudio
    print_ok "PortAudio installed!"
fi

# ==========================================================
# STEP 3: Python virtual environment
# ==========================================================

print_step 3 "Setting up Python environment"

if [ ! -d "$VENV_DIR" ]; then
    echo "  Creating a safe space for the app's code..."
    python3 -m venv "$VENV_DIR"
    print_ok "Python environment created!"
else
    print_skip "Python environment already exists."
fi

echo "  Installing the app's components... (this takes a minute)"

source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet 2>&1 | grep -v "already satisfied"
pip install \
    rauth==0.7.3 \
    "SpeechRecognition>=3.10.0" \
    "PyAudio>=0.2.14" \
    "pynput>=1.7.6" \
    --quiet 2>&1 | grep -v "already satisfied"

print_ok "All components installed!"

# ==========================================================
# STEP 4: E*TRADE API Keys
# ==========================================================

print_step 4 "Setting up your E*TRADE API keys"

CURRENT_KEY=$(grep "CONSUMER_KEY" "$CONFIG_FILE" | head -1 | cut -d'=' -f2 | tr -d ' ')
CURRENT_SECRET=$(grep "CONSUMER_SECRET" "$CONFIG_FILE" | head -1 | cut -d'=' -f2 | tr -d ' ')

if [ "$CURRENT_KEY" = "PLEASE_ENTER_CONSUMER_KEY_HERE" ] || [ -z "$CURRENT_KEY" ]; then
    echo "  You need E*TRADE API keys for this app to work."
    echo "  If you don't have them yet, go to:"
    echo ""
    echo "      https://developer.etrade.com"
    echo ""
    echo "  Log in and create an app to get your Consumer Key"
    echo "  and Consumer Secret."
    echo ""
    echo "  Do you have your API keys ready? (yes/no)"
    read -r HAS_KEYS

    if [[ "$HAS_KEYS" =~ ^[Yy] ]]; then
        echo ""
        echo "  Type or paste your Consumer Key and press Return:"
        read -r USER_KEY

        echo ""
        echo "  Type or paste your Consumer Secret and press Return:"
        read -r USER_SECRET

        if [ -n "$USER_KEY" ] && [ -n "$USER_SECRET" ]; then
            # Use a temp file approach to avoid sed differences between macOS versions
            python3 -c "
content = open('$CONFIG_FILE').read()
content = content.replace('PLEASE_ENTER_CONSUMER_KEY_HERE', '$USER_KEY')
content = content.replace('PLEASE_ENTER_CONSUMER_SECRET_HERE', '$USER_SECRET')
open('$CONFIG_FILE', 'w').write(content)
"
            print_ok "API keys saved!"
        else
            print_warning "Keys looked empty. You can edit them later by opening:"
            echo "         $CONFIG_FILE"
        fi
    else
        echo ""
        echo "  No problem! You can set them up later."
        echo "  When you're ready, open this file in TextEdit:"
        echo ""
        echo "      $CONFIG_FILE"
        echo ""
        echo "  Replace PLEASE_ENTER_CONSUMER_KEY_HERE with your key"
        echo "  and PLEASE_ENTER_CONSUMER_SECRET_HERE with your secret."
    fi
else
    print_skip "API keys are already configured."
fi

# ==========================================================
# STEP 5: Detect foot pedal
# ==========================================================

print_step 5 "Setting up the foot pedal"

echo "  Is the foot pedal plugged in? (yes/no)"
read -r PEDAL_READY

PEDAL_KEY="space"

if [[ "$PEDAL_READY" =~ ^[Yy] ]]; then
    echo ""
    echo "  Great! Let's figure out what key it sends."
    echo "  When you see 'Press the foot pedal now...', step on it."
    echo ""

    wait_for_enter

    DETECTED_KEY=$(timeout 15 python3 -c "
from pynput import keyboard
import sys

def on_press(key):
    try:
        print(key.char, end='')
    except AttributeError:
        name = str(key).replace('Key.', '')
        print(name, end='')
    sys.stdout.flush()
    return False

print('  Press the foot pedal now...', file=sys.stderr)
with keyboard.Listener(on_press=on_press) as listener:
    listener.join()
" 2>&1 | tail -1) || true

    if [ -n "$DETECTED_KEY" ] && [ "$DETECTED_KEY" != "  Press the foot pedal now..." ]; then
        echo ""
        echo ""
        echo "  I detected the key: $DETECTED_KEY"
        PEDAL_KEY="$DETECTED_KEY"
        print_ok "Foot pedal detected as '$PEDAL_KEY'!"
    else
        echo ""
        print_warning "I couldn't detect the pedal. That's OK — we'll default to spacebar."
        echo "  If macOS asked for Input Monitoring permission, grant it,"
        echo "  restart Terminal, and run this setup again."
        PEDAL_KEY="space"
    fi

    # --- Recommend remapping to F13 if the pedal sends a normal key ---
    if [ "$PEDAL_KEY" = "space" ] || [ "$PEDAL_KEY" = "enter" ] || [ ${#PEDAL_KEY} -eq 1 ]; then
        echo ""
        echo "  ------------------------------------------------"
        echo "  IMPORTANT: Your pedal currently sends '$PEDAL_KEY'."
        echo "  That key could accidentally trigger the assistant"
        echo "  during normal typing, or type characters in other"
        echo "  apps when the pedal is pressed."
        echo ""
        echo "  We STRONGLY recommend remapping it to F13 — a key"
        echo "  that doesn't exist on Mac keyboards, so it can't"
        echo "  interfere with anything."
        echo ""
        echo "  Would you like to install Karabiner-Elements"
        echo "  (a free key remapping tool) and set this up? (yes/no)"
        read -r WANTS_REMAP

        if [[ "$WANTS_REMAP" =~ ^[Yy] ]]; then
            echo ""
            echo "  Installing Karabiner-Elements..."

            if ! brew list --cask karabiner-elements &>/dev/null; then
                brew install --cask karabiner-elements
            else
                print_skip "Karabiner-Elements is already installed."
            fi

            # Create a Karabiner config that remaps the detected key to F13
            KARABINER_CONFIG_DIR="$HOME/.config/karabiner/assets/complex_modifications"
            mkdir -p "$KARABINER_CONFIG_DIR"

            if [ "$PEDAL_KEY" = "space" ]; then
                FROM_KEY="spacebar"
            elif [ "$PEDAL_KEY" = "enter" ]; then
                FROM_KEY="return_or_enter"
            else
                FROM_KEY="$PEDAL_KEY"
            fi

            cat > "$KARABINER_CONFIG_DIR/foot_pedal_to_f13.json" << KARABINER_EOF
{
  "title": "Foot Pedal to F13 (for Voice Assistant)",
  "rules": [
    {
      "description": "Remap foot pedal ($PEDAL_KEY) to F13 — only applies to the foot pedal device, not the regular keyboard",
      "manipulators": [
        {
          "type": "basic",
          "from": { "key_code": "$FROM_KEY" },
          "to": [{ "key_code": "f13" }],
          "conditions": [
            {
              "type": "device_if",
              "identifiers": [
                { "is_keyboard": true, "is_pointing_device": false }
              ],
              "description": "NOTE: You need to edit this rule in Karabiner to select ONLY the foot pedal device. Open Karabiner > Complex Modifications > edit this rule."
            }
          ]
        }
      ]
    }
  ]
}
KARABINER_EOF

            echo ""
            echo "  Karabiner-Elements is installed and a remapping"
            echo "  rule has been created."
            echo ""
            echo "  ** IMPORTANT — you still need to do these steps: **"
            echo ""
            echo "  1. Open Karabiner-Elements (search for it in Spotlight)"
            echo "  2. If macOS asks for permissions, grant them"
            echo "  3. Click 'Complex Modifications' in the left sidebar"
            echo "  4. Click 'Add rule'"
            echo "  5. Find 'Foot Pedal to F13' and click 'Enable'"
            echo "  6. Click the rule to edit it — select ONLY the foot"
            echo "     pedal device (not the regular keyboard) so that"
            echo "     the spacebar on the keyboard still works normally"
            echo ""
            echo "  Once that's done, the pedal will send F13 instead"
            echo "  of $PEDAL_KEY, and the voice assistant will use F13."
            echo ""

            PEDAL_KEY="f13"
            print_ok "Voice assistant will be configured to listen for F13."
        else
            echo ""
            echo "  OK, keeping '$PEDAL_KEY' for now."
            echo "  You can remap it later with Karabiner-Elements."
            echo "  See the setup guide for instructions."
        fi
    fi
else
    echo ""
    echo "  No worries! You can set it up later."
    echo "  For now we'll use the spacebar on the keyboard."
    echo "  When the pedal arrives, just plug it in and run"
    echo "  this setup script again."
    PEDAL_KEY="space"
fi

# ==========================================================
# STEP 6: macOS Permissions reminder
# ==========================================================

print_step 6 "macOS Permissions"

echo "  The first time you run the voice assistant, macOS will"
echo "  ask for two permissions:"
echo ""
echo "  1. MICROPHONE — so it can hear Grandpop's voice"
echo "     -> Click 'OK' or 'Allow' when the popup appears"
echo ""
echo "  2. INPUT MONITORING — so it can detect the foot pedal"
echo "     -> Go to System Settings > Privacy & Security"
echo "        > Input Monitoring > turn ON for Terminal"
echo ""
echo "  If you accidentally click 'Don't Allow', here's how to fix it:"
echo "     1. Click the Apple menu (top-left corner)"
echo "     2. Click System Settings"
echo "     3. Click Privacy & Security"
echo "     4. Click Microphone (or Input Monitoring)"
echo "     5. Turn ON the switch next to Terminal"
echo "     6. Close System Settings and restart Terminal"

wait_for_enter

# ==========================================================
# STEP 7: Error alert email
# ==========================================================

print_step 7 "Error alerts"

ALERT_EMAIL="ferris@ferryrules.com"

echo "  If something goes wrong while Grandpop is using the app,"
echo "  an error alert will be sent to: $ALERT_EMAIL"
echo ""
echo "  For this to work, the Mac's Mail app needs to be signed"
echo "  into an email account."

print_ok "Error alerts will go to: $ALERT_EMAIL"

# ==========================================================
# STEP 8: Create shortcut launch scripts
# ==========================================================

print_step 8 "Creating quick-launch shortcuts"

LAUNCH_SCRIPT="$SCRIPT_DIR/start.sh"

ALERT_FLAG=""
if [ -n "$ALERT_EMAIL" ]; then
    ALERT_FLAG=" --alert-email $ALERT_EMAIL"
fi

cat > "$LAUNCH_SCRIPT" << LAUNCH_EOF
#!/bin/bash
# Quick launcher for Grandpop's voice assistant
# Just double-click this file, or run: ./start.sh

cd "$SCRIPT_DIR"
source .venv/bin/activate
cd etrade_python_client
echo ""
echo "  Starting Grandpop's E*TRADE Voice Assistant..."
echo "  Logs are saved in: etrade_python_client/logs/"
echo "  Press Control+C to stop."
echo ""
python3 -u voice_assistant.py --button $PEDAL_KEY$ALERT_FLAG
LAUNCH_EOF

chmod +x "$LAUNCH_SCRIPT"

# Also create a test launcher
TEST_SCRIPT="$SCRIPT_DIR/test.sh"

cat > "$TEST_SCRIPT" << TEST_EOF
#!/bin/bash
# Test the voice assistant with fake data (no E*TRADE login needed)
# Just double-click this file, or run: ./test.sh

cd "$SCRIPT_DIR"
source .venv/bin/activate
cd etrade_python_client
echo ""
echo "  Starting voice assistant in TEST MODE..."
echo "  (Using fake data — no E*TRADE login needed)"
echo "  Press Control+C to stop."
echo ""
python3 -u test_voice.py --button $PEDAL_KEY
TEST_EOF

chmod +x "$TEST_SCRIPT"

print_ok "Created start.sh (real) and test.sh (practice mode)!"

# ==========================================================
# STEP 9: Auto-start on login (LaunchAgent)
# ==========================================================

print_step 9 "Start automatically when the computer turns on"

echo "  Setting up auto-start so the voice assistant launches"
echo "  every time someone logs into this Mac."
echo ""
echo "  Grandpop won't need to find or click anything -"
echo "  it will just be ready when he logs in."
echo "  (Someone will still need to do the E*TRADE login"
echo "  once each day when Chrome opens.)"

{
    PLIST_NAME="com.ferryrules.etrade-voice-assistant"
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$PLIST_DIR/$PLIST_NAME.plist"
    RUNNER_SCRIPT="$SCRIPT_DIR/run_assistant.sh"

    mkdir -p "$PLIST_DIR"

    # Create a runner script that handles updates, venv activation, and logging
    cat > "$RUNNER_SCRIPT" << 'RUNNER_HEADER'
#!/bin/bash
# Auto-start runner for the voice assistant.
# Called by macOS LaunchAgent on login.

RUNNER_HEADER

    cat >> "$RUNNER_SCRIPT" << RUNNER_BODY
SCRIPT_DIR="$SCRIPT_DIR"
RUNNER_BODY

    cat >> "$RUNNER_SCRIPT" << 'RUNNER_REST'
cd "$SCRIPT_DIR"

# Auto-update from GitHub (silent, non-blocking)
if [ -d ".git" ] && command -v git &>/dev/null; then
    timeout 10 git pull --ff-only origin main &>/dev/null 2>&1
    if [ -f ".venv/bin/pip" ]; then
        .venv/bin/pip install -r requirements.txt --quiet 2>/dev/null
    fi
fi

# Activate venv and launch
source .venv/bin/activate
cd etrade_python_client

# Open a real Terminal window so grandpop can hear speech and interact
osascript -e "
tell application \"Terminal\"
    activate
    do script \"cd '$SCRIPT_DIR' && source .venv/bin/activate && cd etrade_python_client && python3 -u voice_assistant.py --button f13 --fallback-button shift\"
end tell
"
RUNNER_REST

    chmod +x "$RUNNER_SCRIPT"

    # Create the LaunchAgent plist
    cat > "$PLIST_FILE" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$RUNNER_SCRIPT</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/etrade_python_client/logs/launchagent_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/etrade_python_client/logs/launchagent_stderr.log</string>
</dict>
</plist>
PLIST_EOF

    # Load the agent (won't start until next login, or we can start it now)
    launchctl unload "$PLIST_FILE" 2>/dev/null
    launchctl load "$PLIST_FILE"

    print_ok "Auto-start is set up!"
    echo ""
    echo "  The voice assistant will now start automatically"
    echo "  every time someone logs into this Mac."
    echo ""
    echo "  To stop auto-start later, run:"
    echo "    launchctl unload ~/Library/LaunchAgents/$PLIST_NAME.plist"
}

# ==========================================================
# Done!
# ==========================================================

echo ""
echo "  =================================================="
echo "  Setup complete!"
echo "  =================================================="
echo ""
echo "  WHAT'S NEXT:"
echo ""
echo "  1. TEST IT (no E*TRADE login needed):"
echo "     Go to the EtradePythonClient folder in Downloads"
echo "     and double-click 'Test Voice Assistant'."
echo ""
echo "     Press the foot pedal (or spacebar) and ask:"
echo "     'What's the price of Apple?'"
echo ""
echo "  2. RUN FOR REAL (needs E*TRADE login):"
echo "     Go to the EtradePythonClient folder in Downloads"
echo "     and double-click 'Start Voice Assistant'."
echo ""
echo "  =================================================="
echo ""
echo "  LOGS & TRANSCRIPTS:"
echo "    Every session is saved in:"
echo "      ~/Downloads/EtradePythonClient/etrade_python_client/logs/"
echo "    Each file contains a full transcript of what"
echo "    Grandpop asked and what the app said back,"
echo "    plus any errors that happened."
echo ""
echo "  ERROR ALERTS:"
echo "    If something goes wrong, an email will be sent to:"
echo "      $ALERT_EMAIL"
echo ""
echo "  =================================================="
echo ""
echo "  DAILY CHEAT SHEET (tape this near the computer!):"
echo ""
echo "    1. Turn on the computer and log in"
echo "    2. The voice assistant starts automatically!"
echo "    3. When Chrome opens, log in to E*TRADE"
echo "    4. Read the verification code out loud"
echo "    5. Press foot pedal to ask questions!"
echo "    6. Press Control+C in the Terminal window when done"
echo ""
echo "  =================================================="
echo ""
