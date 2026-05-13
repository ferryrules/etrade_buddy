#!/usr/bin/env bash
# Diagnose why the Chrome verifier auto-detect isn't seeing the page.
# Run this in a SECOND Terminal window while the assistant is sitting at
# "I'll watch the page..." with the E*TRADE verifier code visible in Chrome.
#
# It will show, in order:
#   1. Does AppleScript see Chrome at all?
#   2. What's the URL of the active tab?
#   3. What's the title of the active tab?
#   4. Can AppleScript run JavaScript? (the critical question)
#   5. If yes, what text does Chrome think is on the page?
#   6. Does our regex actually find the verifier in that text?

set -u

echo "=== 1. Is Chrome running? ==="
osascript -e 'tell application "System Events" to (name of processes) contains "Google Chrome"'
echo

echo "=== 2. Active tab URL ==="
osascript -e 'tell application "Google Chrome" to URL of active tab of front window' 2>&1
echo

echo "=== 3. Active tab title ==="
osascript -e 'tell application "Google Chrome" to title of active tab of front window' 2>&1
echo

echo "=== 4. Can AppleScript run JavaScript in Chrome? ==="
JS_TEST=$(osascript -e 'tell application "Google Chrome" to execute active tab of front window javascript "1 + 1"' 2>&1)
echo "Result: $JS_TEST"
echo

echo "=== 5. Page text via the NEW extractor JS (innerText + input/textarea values) ==="
JS="(function(){var t=document.body?document.body.innerText:'';var e=document.querySelectorAll('input,textarea');for(var i=0;i<e.length;i++){if(e[i].value)t+=' '+e[i].value;}return t;})()"
PAGE_TEXT=$(osascript -e "tell application \"Google Chrome\" to execute active tab of front window javascript \"$JS\"" 2>&1)
echo "$PAGE_TEXT" | head -c 2000
echo
echo "..."
echo

echo "=== 6. Does the assistant's NEW regex find a verifier in that text? ==="
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/.venv/bin/python" - <<PYEOF
import sys
sys.path.insert(0, "$SCRIPT_DIR/etrade_python_client")
from voice_assistant import ETradeVoiceAssistant
text = """$PAGE_TEXT"""
print("Length of page text:", len(text))
print("Contains 'verif' (case-ins):", "verif" in text.lower())
print("Extractor result:", ETradeVoiceAssistant._extract_verifier_from_page(text))
PYEOF
