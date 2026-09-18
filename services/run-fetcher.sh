#!/bin/bash
# Wrapper script to run fetcher for 15 minutes

set -e

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Activate virtual environment
source "$PROJECT_ROOT/venv/bin/activate"

# Run fetcher for 15 minutes (900 seconds), then send SIGTERM for graceful shutdown
cd "$PROJECT_ROOT/pipeline/fetcher"

# Start the fetcher in the background
python3 main.py &
FETCHER_PID=$!

# Wait for 15 minutes (900 seconds) or until the process exits
(
    sleep 900
    # If the process is still running after 15 minutes, send SIGTERM
    if kill -0 $FETCHER_PID 2>/dev/null; then
        echo "15-minute time limit reached, stopping fetcher gracefully..."
        kill -TERM $FETCHER_PID
    fi
) &
TIMER_PID=$!

# Wait for the fetcher process to complete
wait $FETCHER_PID
EXIT_CODE=$?

# Kill the timer if it's still running
kill $TIMER_PID 2>/dev/null || true

# Check exit code
if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 143 ]; then
    echo "Fetcher completed successfully"
    exit 0
else
    echo "Fetcher exited with error code: $EXIT_CODE"
    exit $EXIT_CODE
fi
