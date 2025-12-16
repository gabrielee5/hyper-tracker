#!/bin/bash
# Start Hyper Tracker scout services (fetcher + analyzer)

set -e

# Get the project root directory (parent of services/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting Hyper Tracker Scout services..."
echo ""

# Make wrapper script executable
chmod +x "$PROJECT_ROOT/services/run-fetcher.sh"

# Copy plist files to LaunchAgents directory
echo "Installing launch agents..."
cp "$PROJECT_ROOT/services/com.hyper-tracker.fetcher.plist" ~/Library/LaunchAgents/
cp "$PROJECT_ROOT/services/com.hyper-tracker.analyzer.plist" ~/Library/LaunchAgents/

# Load and start services
echo "Starting fetcher service (runs hourly for 15 minutes)..."
launchctl load ~/Library/LaunchAgents/com.hyper-tracker.fetcher.plist 2>/dev/null || \
    launchctl start com.hyper-tracker.fetcher

echo "Starting analyzer service (continuous)..."
launchctl load ~/Library/LaunchAgents/com.hyper-tracker.analyzer.plist 2>/dev/null || \
    launchctl start com.hyper-tracker.analyzer

# Prevent Mac from sleeping
echo "Preventing Mac from sleeping..."
caffeinate -s &
CAFFEINATE_PID=$!
echo $CAFFEINATE_PID > "$PROJECT_ROOT/services/.caffeinate-scout.pid"

echo ""
echo "✓ Scout services started successfully!"
echo ""
echo "Scout services are now running in the background:"
echo "  - Fetcher: Runs at the start of every hour for 15 minutes"
echo "  - Analyzer: Running continuously"
echo ""
echo "They will auto-restart if they crash and start on boot."
echo "Mac sleep has been DISABLED to keep services running."
echo ""
echo "To stop services, run: ./stop-scout.sh"
echo "To check status, run: ./status-scout.sh"
