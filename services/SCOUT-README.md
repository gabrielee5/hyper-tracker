# Hyper Tracker Scout Services

Scout services handle data collection and analysis for the Hyper Tracker system.

## Services Overview

### 1. Fetcher Service
- **Purpose**: Collects trader addresses from Hyperliquid
- **Schedule**: Runs at the beginning of every hour (minute 0)
- **Duration**: Active for exactly 15 minutes per hour
- **Implementation**: Wrapper script with `timeout` command enforces 15-minute limit
- **Script**: `fetcher/main.py`
- **Logs**:
  - `logs/fetcher-stdout.log`
  - `logs/fetcher-stderr.log`

### 2. Analyzer Service
- **Purpose**: Performs continuous statistical analysis on trader performance
- **Schedule**: Runs continuously
- **Auto-restart**: Yes (via KeepAlive)
- **Mode**: Continuous analysis mode (`--mode continuous`)
- **Script**: `analyzer/main.py`
- **Logs**:
  - `logs/analyzer-stdout.log`
  - `logs/analyzer-stderr.log`

## Quick Start

```bash
# Navigate to services directory
cd /Users/gabrielefabietti/projects/hyper-tracker/services

# Start both scout services
./start-scout.sh

# Check status
./status-scout.sh

# Stop both scout services
./stop-scout.sh

# Restart both scout services
./restart-scout.sh
```

## How It Works

### Fetcher Hourly Schedule

The fetcher runs on an hourly schedule:
- **:00** - Starts fetching (e.g., 13:00, 14:00, 15:00)
- **:00 to :15** - Active for 15 minutes
- **:15** - Automatically stops via timeout
- **:15 to :59** - Idle, waiting for next hour
- **:00** - Starts again

This schedule ensures:
- Fresh data every hour
- Minimal resource usage (only 15 min/hour = 25% duty cycle)
- No overlap between cycles
- Predictable data collection windows

### Analyzer Continuous Operation

The analyzer runs 24/7:
- Monitors database for new traders
- Performs statistical analysis continuously
- Auto-restarts if it crashes
- Processes data as it becomes available from fetcher

### Sleep Prevention

When you start scout services, Mac sleep is automatically prevented using `caffeinate`:
- **Display can sleep** - screen will turn off
- **System stays awake** - services keep running
- **PID tracked** - stored in `.caffeinate-scout.pid`
- **Auto cleanup** - stopped when you run `./stop-scout.sh`

## Service Files

- `com.hyper-tracker.fetcher.plist` - Fetcher launchd configuration
- `com.hyper-tracker.analyzer.plist` - Analyzer launchd configuration
- `run-fetcher.sh` - Wrapper script that enforces 15-minute timeout
- `start-scout.sh` - Start both services
- `stop-scout.sh` - Stop both services
- `status-scout.sh` - Check service status
- `restart-scout.sh` - Restart both services

## Viewing Logs

```bash
# Fetcher logs (real-time)
tail -f logs/fetcher-stdout.log

# Analyzer logs (real-time)
tail -f logs/analyzer-stdout.log

# All scout logs
tail -f logs/fetcher-stdout.log logs/analyzer-stdout.log

# Check for errors
tail -f logs/fetcher-stderr.log logs/analyzer-stderr.log
```

## Manual Service Control

Using `launchctl` directly:

```bash
# Check if services are loaded
launchctl list | grep hyper-tracker

# Start individual services
launchctl start com.hyper-tracker.fetcher
launchctl start com.hyper-tracker.analyzer

# Stop individual services
launchctl stop com.hyper-tracker.fetcher
launchctl stop com.hyper-tracker.analyzer

# Completely remove services
launchctl unload ~/Library/LaunchAgents/com.hyper-tracker.fetcher.plist
launchctl unload ~/Library/LaunchAgents/com.hyper-tracker.analyzer.plist
```

## Typical Workflow

### Start collecting data
```bash
cd services
./start-scout.sh
```

The fetcher will:
- Run immediately (RunAtLoad=true)
- Then run every hour at :00
- Collect data for 15 minutes
- Stop automatically after 15 minutes

The analyzer will:
- Start immediately
- Run continuously
- Process traders as they're added by fetcher

### Monitor progress
```bash
./status-scout.sh
```

### Stop when done
```bash
./stop-scout.sh
```

## Troubleshooting

### Fetcher not running at expected times
1. Check system time is correct: `date`
2. Verify service is loaded: `launchctl list | grep fetcher`
3. Check logs: `tail -f logs/fetcher-stdout.log`
4. Manually trigger: `launchctl start com.hyper-tracker.fetcher`

### Analyzer keeps restarting
1. Check error log: `tail -f logs/analyzer-stderr.log`
2. Verify database exists and is accessible
3. Check configuration: `ls -la analyzer/config.yaml`
4. Test manually: `cd analyzer && python3 main.py --mode continuous`

### Fetcher runs longer than 15 minutes
This shouldn't happen due to the `timeout` wrapper, but if it does:
1. Check `run-fetcher.sh` has timeout command
2. Verify timeout is available: `which timeout`
3. Check if timeout is working: `timeout 5 sleep 10` (should exit after 5 sec)

### Services won't start
1. Check plist syntax: `plutil -lint ~/Library/LaunchAgents/com.hyper-tracker.fetcher.plist`
2. Verify Python path: `ls -la /Users/gabrielefabietti/projects/hyper-tracker/venv/bin/python3`
3. Check permissions: `chmod +x services/run-fetcher.sh`
4. View system logs: `tail -f /var/log/system.log | grep hyper-tracker`

## Configuration

### Fetcher Timing
To change when the fetcher runs, edit `com.hyper-tracker.fetcher.plist`:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Minute</key>
    <integer>0</integer>  <!-- Change this to run at different minute -->
</dict>
```

Then restart the service:
```bash
./restart-scout.sh
```

### Fetcher Duration
To change how long the fetcher runs, edit `run-fetcher.sh`:

```bash
# Change 900 (15 minutes in seconds)
timeout 900 "$PROJECT_ROOT/venv/bin/python3" ...
```

Common values:
- 300 = 5 minutes
- 600 = 10 minutes
- 900 = 15 minutes (current)
- 1800 = 30 minutes

### Analyzer Mode
The analyzer runs in continuous mode by default. To change, edit `com.hyper-tracker.analyzer.plist`:

```xml
<key>ProgramArguments</key>
<array>
    <string>/Users/gabrielefabietti/projects/hyper-tracker/venv/bin/python3</string>
    <string>/Users/gabrielefabietti/projects/hyper-tracker/analyzer/main.py</string>
    <string>--mode</string>
    <string>continuous</string>  <!-- or 'once' -->
</array>
```

## Best Practices

1. **Monitor initially**: Watch logs for the first few hours to ensure everything works
2. **Check hourly**: Verify fetcher runs at the start of each hour
3. **Database backups**: Scout services write to the database - back it up regularly
4. **Clean shutdown**: Always use `./stop-scout.sh` before making code changes
5. **Restart after updates**: Run `./restart-scout.sh` after updating fetcher or analyzer code

## Summary

Scout services provide automated data collection and analysis:
- **Fetcher**: Hourly 15-minute data collection cycles
- **Analyzer**: Continuous statistical analysis
- **Automatic**: Set and forget operation
- **Resilient**: Auto-restart on crashes
- **Logged**: All activity tracked in log files
