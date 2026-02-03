#!/bin/bash
# Stop hyper-tracker contrarian service

# Get the project root directory (parent of services/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Stopping Hyper Tracker contrarian service..."
echo ""

# Stop and unload service
echo "Stopping contrarian service..."
launchctl stop com.hyper-tracker.contrarian 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.hyper-tracker.contrarian.plist 2>/dev/null || true

# Re-enable Mac sleep
if [ -f "$PROJECT_ROOT/services/.caffeinate.pid" ]; then
    echo "Re-enabling Mac sleep..."
    CAFFEINATE_PID=$(cat "$PROJECT_ROOT/services/.caffeinate.pid")
    kill $CAFFEINATE_PID 2>/dev/null || true
    rm "$PROJECT_ROOT/services/.caffeinate.pid"
fi

echo ""
echo "✓ Contrarian service stopped successfully!"
echo ""
echo "Service will NOT restart on boot until you run ./start-services.sh again"
echo "Mac sleep has been RE-ENABLED"
