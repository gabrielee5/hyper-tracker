#!/bin/bash
# Check status of Hyper Tracker scout services (fetcher + analyzer)

# Get the project root directory (parent of services/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==================================================================="
echo "HYPER TRACKER SCOUT SERVICES STATUS"
echo "==================================================================="
echo ""

# Check fetcher service
echo "📥 FETCHER SERVICE (runs hourly for 15 min):"
if launchctl list | grep -q "com.hyper-tracker.fetcher"; then
    PID=$(launchctl list | grep com.hyper-tracker.fetcher | awk '{print $1}')
    if [ "$PID" != "-" ]; then
        echo "   Status: ✅ RUNNING (active cycle)"
        echo "   PID: $PID"
    else
        echo "   Status: ⏱️  SCHEDULED (waiting for next hour)"
    fi
else
    echo "   Status: ❌ STOPPED"
fi
echo ""

# Check analyzer service
echo "🔬 ANALYZER SERVICE (continuous):"
if launchctl list | grep -q "com.hyper-tracker.analyzer"; then
    echo "   Status: ✅ RUNNING"
    echo "   PID: $(launchctl list | grep com.hyper-tracker.analyzer | awk '{print $1}')"
else
    echo "   Status: ❌ STOPPED"
fi
echo ""

# Check sleep prevention
echo "💤 SLEEP PREVENTION:"
if [ -f "$PROJECT_ROOT/services/.caffeinate-scout.pid" ]; then
    CAFFEINATE_PID=$(cat "$PROJECT_ROOT/services/.caffeinate-scout.pid")
    if ps -p $CAFFEINATE_PID > /dev/null 2>&1; then
        echo "   Status: ✅ ACTIVE (Mac won't sleep)"
        echo "   PID: $CAFFEINATE_PID"
    else
        echo "   Status: ⚠️  PID file exists but process not running"
    fi
else
    echo "   Status: ❌ INACTIVE (Mac can sleep)"
fi
echo ""

echo "==================================================================="
echo "LOGS"
echo "==================================================================="
echo ""
echo "Fetcher stdout:    $PROJECT_ROOT/logs/fetcher-stdout.log"
echo "Fetcher stderr:    $PROJECT_ROOT/logs/fetcher-stderr.log"
echo "Analyzer stdout:   $PROJECT_ROOT/logs/analyzer-stdout.log"
echo "Analyzer stderr:   $PROJECT_ROOT/logs/analyzer-stderr.log"
echo ""
echo "View live logs:"
echo "  tail -f $PROJECT_ROOT/logs/fetcher-stdout.log"
echo "  tail -f $PROJECT_ROOT/logs/analyzer-stdout.log"
echo ""
