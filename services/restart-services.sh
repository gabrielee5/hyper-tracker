#!/bin/bash
# Restart both hyper-tracker services

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Restarting Hyper Tracker services..."
echo ""

"$SCRIPT_DIR/stop-services.sh"
sleep 2
"$SCRIPT_DIR/start-services.sh"
