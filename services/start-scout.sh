#!/bin/bash
# Start Hyper Tracker scout services (fetcher + analyzer)

set -e

# Parse command line arguments
MINUTE=0
while [[ $# -gt 0 ]]; do
    case $1 in
        --minute)
            MINUTE="$2"
            shift 2
            ;;
        -m)
            MINUTE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--minute MINUTE]"
            echo ""
            echo "Options:"
            echo "  --minute, -m MINUTE   Minute of the hour to run fetcher (0-59, default: 0)"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Example: $0 --minute 30    # Run fetcher at 30 minutes past each hour"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate minute
if ! [[ "$MINUTE" =~ ^[0-9]+$ ]] || [ "$MINUTE" -lt 0 ] || [ "$MINUTE" -gt 59 ]; then
    echo "Error: Minute must be a number between 0 and 59"
    exit 1
fi

# Get the project root directory (parent of services/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting Hyper Tracker Scout services..."
echo ""

# Make wrapper script executable
chmod +x "$PROJECT_ROOT/services/run-fetcher.sh"

# Copy plist files to LaunchAgents directory
echo "Installing launch agents..."
echo "  - Fetcher will run at minute $MINUTE of each hour"

# Install both agents, substituting the repo path into the templates.
# The fetcher plist also gets its schedule minute rewritten.
mkdir -p ~/Library/LaunchAgents "$PROJECT_ROOT/logs"

sed -e "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
    -e "s|<integer>0</integer>|<integer>$MINUTE</integer>|" \
    "$PROJECT_ROOT/services/com.hyper-tracker.fetcher.plist" > \
    ~/Library/LaunchAgents/com.hyper-tracker.fetcher.plist

sed "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
    "$PROJECT_ROOT/services/com.hyper-tracker.analyzer.plist" > \
    ~/Library/LaunchAgents/com.hyper-tracker.analyzer.plist

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
echo "  - Fetcher: Runs at minute $MINUTE of every hour for 15 minutes"
echo "  - Analyzer: Running continuously"
echo ""
echo "They will auto-restart if they crash and start on boot."
echo "Mac sleep has been DISABLED to keep services running."
echo ""
echo "To stop services, run: ./stop-scout.sh"
echo "To check status, run: ./status-scout.sh"
