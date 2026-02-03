#!/bin/bash
# Start hyper-tracker contrarian service

set -e

# Get the project root directory (parent of services/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting Hyper Tracker contrarian service..."
echo ""

# Copy plist file to LaunchAgents directory
echo "Installing launch agent..."
cp "$PROJECT_ROOT/services/com.hyper-tracker.contrarian.plist" ~/Library/LaunchAgents/

# Load and start service
echo "Starting contrarian service..."
launchctl load ~/Library/LaunchAgents/com.hyper-tracker.contrarian.plist 2>/dev/null || \
    launchctl start com.hyper-tracker.contrarian

# Prevent Mac from sleeping
echo "Preventing Mac from sleeping..."
caffeinate -s &
CAFFEINATE_PID=$!
echo $CAFFEINATE_PID > "$PROJECT_ROOT/services/.caffeinate.pid"

echo ""
echo "✓ Contrarian service started successfully!"
echo ""
echo "Service is now running in the background."
echo "It will auto-restart if it crashes and start on boot."
echo "Mac sleep has been DISABLED to keep service running."
echo ""
echo "To stop services, run: ./stop-services.sh"
echo "To check status, run: ./status-services.sh"
