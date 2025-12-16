#!/bin/bash
# Stop Hyper Tracker scout services (fetcher + analyzer)

# Get the project root directory (parent of services/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Stopping Hyper Tracker Scout services..."
echo ""

# Stop and unload services
echo "Stopping fetcher service..."
launchctl stop com.hyper-tracker.fetcher 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.hyper-tracker.fetcher.plist 2>/dev/null || true

echo "Stopping analyzer service..."
launchctl stop com.hyper-tracker.analyzer 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.hyper-tracker.analyzer.plist 2>/dev/null || true

# Re-enable Mac sleep
if [ -f "$PROJECT_ROOT/services/.caffeinate-scout.pid" ]; then
    echo "Re-enabling Mac sleep..."
    CAFFEINATE_PID=$(cat "$PROJECT_ROOT/services/.caffeinate-scout.pid")
    kill $CAFFEINATE_PID 2>/dev/null || true
    rm "$PROJECT_ROOT/services/.caffeinate-scout.pid"
fi

echo ""
echo "✓ Scout services stopped successfully!"
echo ""
echo "Services will NOT restart on boot until you run ./start-scout.sh again"
echo "Mac sleep has been RE-ENABLED"
