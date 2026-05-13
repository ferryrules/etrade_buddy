#!/usr/bin/env bash
# =============================================================================
# Optional: detect what key your USB foot pedal sends, and (recommended)
# install Karabiner-Elements to remap it to F13 so it can never accidentally
# type a space/enter into another app.
#
# Run this AFTER ./install.sh, only if your pedal sends a key other than F13.
# It will print which key your pedal sends and update the LaunchAgent to use it.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PLIST_NAME="com.ferryrules.etrade-voice-assistant"
PLIST_FILE="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

if [[ ! -d "$VENV_DIR" ]]; then
    echo "  [!] Run ./install.sh first."
    exit 1
fi

echo
echo "  ============================================================"
echo "  Foot pedal setup"
echo "  ============================================================"
echo
echo "  Make sure the pedal is plugged in. When you see"
echo "  'Press the foot pedal now...' below, press it once."
echo
read -rp "  Press Return when ready..."

DETECTED_KEY=$(timeout 15 "$VENV_DIR/bin/python" - <<'PY' 2>&1 | tail -1 || true
from pynput import keyboard
import sys
def on_press(key):
    try:
        print(key.char, end='')
    except AttributeError:
        print(str(key).replace('Key.', ''), end='')
    sys.stdout.flush()
    return False
print('  Press the foot pedal now...', file=sys.stderr)
with keyboard.Listener(on_press=on_press) as listener:
    listener.join()
PY
)

if [[ -z "$DETECTED_KEY" || "$DETECTED_KEY" == *"Press the foot pedal now"* ]]; then
    echo
    echo "  [!] Couldn't detect the pedal."
    echo "      Most likely cause: macOS hasn't granted Input Monitoring to Terminal."
    echo "      Fix it in: System Settings -> Privacy & Security -> Input Monitoring"
    echo "      then re-run this script."
    exit 1
fi

echo
echo "  [ok] Detected key: $DETECTED_KEY"
echo

# Strongly recommend remapping if it's a normal typing key
if [[ "$DETECTED_KEY" == "space" || "$DETECTED_KEY" == "enter" || ${#DETECTED_KEY} -eq 1 ]]; then
    echo "  Your pedal sends '$DETECTED_KEY', which is a normal typing key."
    echo "  We strongly recommend remapping it to F13 (a key that doesn't exist"
    echo "  on Mac keyboards, so it can't accidentally type into other apps)."
    echo
    read -rp "  Install Karabiner-Elements and create the remap rule? [y/N] " WANTS_REMAP
    if [[ "$WANTS_REMAP" =~ ^[Yy] ]]; then
        if ! command -v brew &>/dev/null; then
            echo "  [!] Homebrew missing. Run ./install.sh first."
            exit 1
        fi
        brew list --cask karabiner-elements &>/dev/null || brew install --cask karabiner-elements

        KARABINER_DIR="$HOME/.config/karabiner/assets/complex_modifications"
        mkdir -p "$KARABINER_DIR"

        case "$DETECTED_KEY" in
            space) FROM_KEY="spacebar" ;;
            enter) FROM_KEY="return_or_enter" ;;
            *)     FROM_KEY="$DETECTED_KEY" ;;
        esac

        cat > "$KARABINER_DIR/foot_pedal_to_f13.json" <<KARABINER_EOF
{
  "title": "Foot Pedal to F13 (E*TRADE Voice Assistant)",
  "rules": [
    {
      "description": "Remap foot pedal ($DETECTED_KEY) to F13 — edit in Karabiner to scope to ONLY the foot pedal device",
      "manipulators": [
        {
          "type": "basic",
          "from": { "key_code": "$FROM_KEY" },
          "to":   [{ "key_code": "f13" }]
        }
      ]
    }
  ]
}
KARABINER_EOF
        echo
        echo "  [ok] Karabiner config written. Now finish the setup in Karabiner:"
        echo "       1. Open Karabiner-Elements (Spotlight)"
        echo "       2. Grant any permissions it asks for"
        echo "       3. Complex Modifications -> Add rule -> enable 'Foot Pedal to F13'"
        echo "       4. Edit the rule to scope it to ONLY the foot pedal device"
        echo "          (so the spacebar on the keyboard still works normally)"
        echo
        echo "  After that, the LaunchAgent's default --button f13 will Just Work."
        exit 0
    fi
fi

# No remap requested — patch the LaunchAgent to use the detected key directly
if [[ ! -f "$PLIST_FILE" ]]; then
    echo "  [!] LaunchAgent missing. Run ./install.sh first."
    exit 1
fi

# Replace the value of the --button argument in the plist using PlistBuddy
/usr/libexec/PlistBuddy -c "Print :ProgramArguments" "$PLIST_FILE" >/dev/null
ARG_INDEX=0
while IFS= read -r line; do
    if [[ "$line" == "    --button" ]]; then
        TARGET=$((ARG_INDEX + 1))
        /usr/libexec/PlistBuddy -c "Set :ProgramArguments:$TARGET $DETECTED_KEY" "$PLIST_FILE"
        break
    fi
    ARG_INDEX=$((ARG_INDEX + 1))
done < <(/usr/libexec/PlistBuddy -c "Print :ProgramArguments" "$PLIST_FILE" | sed '1d;$d')

launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"
echo "  [ok] LaunchAgent now uses --button $DETECTED_KEY. Restarted."
