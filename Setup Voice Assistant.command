#!/bin/bash
# =====================================================
# Double-click this file to set up the voice assistant.
# =====================================================

# Move to the folder this file lives in, no matter where it was clicked from
cd "$(dirname "$0")"

echo ""
echo "  Starting setup..."
echo ""

# Hand off to the real setup script
./setup_voice.sh

# Keep the window open so they can read the final output
echo ""
echo ""
echo "  =================================================="
echo "  You can close this window now."
echo "  =================================================="
echo ""
read -r -p "  Press Return to close..."
