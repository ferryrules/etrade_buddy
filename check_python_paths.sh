#!/usr/bin/env bash
# Show the real Python binary path that macOS TCC checks against, so we can
# grant Accessibility / Input Monitoring permission to the right thing.
set -u

VENV_PY="/Users/ferry/etrade_buddy/.venv/bin/python"

echo "=== As you'd run it ==="
echo "  $VENV_PY"
echo "  symlink target: $(readlink "$VENV_PY" 2>/dev/null || echo '(not a symlink)')"
echo

echo "=== Fully resolved real path (this is what TCC checks) ==="
REALPATH=$(/usr/bin/python3 -c "import os, sys; print(os.path.realpath(sys.argv[1]))" "$VENV_PY")
echo "  $REALPATH"
echo

echo "=== Also resolve python3 ==="
PY3_REALPATH=$(/usr/bin/python3 -c "import os, sys; print(os.path.realpath('/Users/ferry/etrade_buddy/.venv/bin/python3'))")
echo "  /Users/ferry/etrade_buddy/.venv/bin/python3 -> $PY3_REALPATH"
echo

echo "=== sys.executable while actually running the venv Python ==="
"$VENV_PY" -c "import sys; print('  sys.executable =', sys.executable); print('  sys.base_prefix =', sys.base_prefix)"
echo

echo "=== Currently granted Accessibility entries (requires admin password to read fully) ==="
echo "  Open: System Settings -> Privacy & Security -> Accessibility"
echo "  Make sure BOTH of these are listed AND toggled ON:"
echo "    1. $VENV_PY"
echo "    2. $REALPATH"
echo
echo "  If they're not, click '+' and add them. For path 2, you may need to:"
echo "    - Press Cmd+Shift+G (Go to Folder) in the file picker"
echo "    - Paste the path"
echo "    - Click Open, then check the box"
