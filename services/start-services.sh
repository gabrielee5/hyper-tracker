#!/bin/bash
# Start both hyper-tracker services

set -e

# Get the project root directory (parent of services/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting Hyper Tracker services..."
echo ""

# Copy plist files to LaunchAgents directory
echo "Installing launch agents..."
cp "$PROJECT_ROOT/services/com.hyper-tracker.contrarian.plist" ~/Library/LaunchAgents/
cp "$PROJECT_ROOT/services/com.hyper-tracker.simulator.plist" ~/Library/LaunchAgents/

# Load and start services
echo "Starting contrarian service..."
launchctl load ~/Library/LaunchAgents/com.hyper-tracker.contrarian.plist 2>/dev/null || \
    launchctl start com.hyper-tracker.contrarian

echo "Starting simulator service..."
launchctl load ~/Library/LaunchAgents/com.hyper-tracker.simulator.plist 2>/dev/null || \
    launchctl start com.hyper-tracker.simulator

# Prevent Mac from sleeping
echo "Preventing Mac from sleeping..."
caffeinate -s &
CAFFEINATE_PID=$!
echo $CAFFEINATE_PID > "$PROJECT_ROOT/services/.caffeinate.pid"

echo ""
echo "✓ Services started successfully!"
echo ""
echo "Both services are now running in the background."
echo "They will auto-restart if they crash and start on boot."
echo "Mac sleep has been DISABLED to keep services running."
echo ""
echo "To stop services, run: ./stop-services.sh"
echo "To check status, run: ./status-services.sh"
