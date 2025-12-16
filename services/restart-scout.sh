#!/bin/bash
# Restart Hyper Tracker scout services (fetcher + analyzer)

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Restarting Hyper Tracker Scout services..."
echo ""

# Stop services
"$SCRIPT_DIR/stop-scout.sh"

echo ""
echo "Waiting 3 seconds before starting services..."
sleep 3
echo ""

# Start services with all arguments passed through
"$SCRIPT_DIR/start-scout.sh" "$@"
