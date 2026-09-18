#!/bin/bash
# Check status of hyper-tracker services

# Get the project root directory (parent of services/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==================================================================="
echo "HYPER TRACKER SERVICES STATUS"
echo "==================================================================="
echo ""

# Check contrarian service
echo "📊 CONTRARIAN SERVICE:"
if launchctl list | grep -q "com.hyper-tracker.contrarian"; then
    echo "   Status: ✅ RUNNING"
    echo "   PID: $(launchctl list | grep com.hyper-tracker.contrarian | awk '{print $1}')"
else
    echo "   Status: ❌ STOPPED"
fi
echo ""

# Check sleep prevention
echo "💤 SLEEP PREVENTION:"
if [ -f "$PROJECT_ROOT/services/.caffeinate.pid" ]; then
    CAFFEINATE_PID=$(cat "$PROJECT_ROOT/services/.caffeinate.pid")
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
echo "Contrarian stdout: $PROJECT_ROOT/logs/contrarian-stdout.log"
echo "Contrarian stderr: $PROJECT_ROOT/logs/contrarian-stderr.log"
echo ""
echo "View live logs:"
echo "  tail -f $PROJECT_ROOT/logs/contrarian-stdout.log"
echo ""
