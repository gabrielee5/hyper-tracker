# Hyper Tracker Background Services

This document explains how to run the Contrarian and Simulator services perpetually on macOS using launchd.

## Overview

The services are configured to run in the background using macOS's native `launchd` system. This allows them to:
- Run continuously in the background
- Auto-restart if they crash
- Start automatically on Mac reboot
- Keep running even when Terminal is closed

## Quick Start

```bash
# Navigate to the services directory
cd services/

# Start both services (run once, they'll keep running)
./start-services.sh

# Check if they're running
./status-services.sh

# Stop both services (when you're back at your Mac)
./stop-services.sh

# Restart both services
./restart-services.sh
```

## How It Works

### When you START (`./start-services.sh`):
- Both scripts run in the background immediately
- They auto-restart if they crash
- They'll start automatically on Mac reboot
- You can close Terminal, log out, etc. - they keep running
- **Mac sleep is DISABLED** - your Mac will stay awake to keep services running

### When you STOP (`./stop-services.sh`):
- Both scripts stop immediately
- They won't restart on crash
- They won't start on reboot
- **Mac sleep is RE-ENABLED** - your Mac can sleep normally again
- Completely stopped until you run `./start-services.sh` again

## Services

### 1. Contrarian Service
- **Script:** `../contrarian/main.py`
- **Purpose:** Monitors bad traders and generates contrarian signals
- **Web Dashboard:** http://127.0.0.1:5000 (when running)

### 2. Simulator Service
- **Script:** `../simulator/main_three_asset.py`
- **Purpose:** Three-asset paper trading simulator (BTC, SOL, ETH only) that executes trades based on signals
- **Web Dashboard:** http://localhost:8050 (when running)

## Logs

All output is redirected to separate log files in the `../logs/` directory:

- `../logs/contrarian-stdout.log` - Contrarian service output
- `../logs/contrarian-stderr.log` - Contrarian errors
- `../logs/simulator-stdout.log` - Simulator output
- `../logs/simulator-stderr.log` - Simulator errors

### View Live Logs

```bash
# Watch contrarian logs in real-time
tail -f ../logs/contrarian-stdout.log

# Watch simulator logs in real-time
tail -f ../logs/simulator-stdout.log

# Watch errors
tail -f ../logs/contrarian-stderr.log
tail -f ../logs/simulator-stderr.log
```

## Typical Workflow

1. **Before leaving your Mac:**
   ```bash
   cd services/
   ./start-services.sh
   ```

2. **Walk away** - services run perpetually

3. **When you return:**
   ```bash
   cd services/
   ./status-services.sh
   ```
   Check that everything is running smoothly

4. **When done testing:**
   ```bash
   cd services/
   ./stop-services.sh
   ```

## What Survives?

The services will continue running through:
- ✅ Terminal closing
- ✅ Logging out
- ✅ Mac reboot (they auto-start)
- ✅ Crashes (they auto-restart)
- ✅ Mac sleep (prevented by `caffeinate`)

They'll only stop when you:
- ❌ Explicitly run `./stop-services.sh`
- ❌ Manually unload the launch agents
- ❌ Mac shuts down completely (power off)

## Manual Management

If you need to manage services manually using `launchctl`:

### Check Status
```bash
launchctl list | grep hyper-tracker
```

### Start Individual Services
```bash
launchctl start com.hyper-tracker.contrarian
launchctl start com.hyper-tracker.simulator
```

### Stop Individual Services
```bash
launchctl stop com.hyper-tracker.contrarian
launchctl stop com.hyper-tracker.simulator
```

### Completely Uninstall
```bash
launchctl unload ~/Library/LaunchAgents/com.hyper-tracker.contrarian.plist
launchctl unload ~/Library/LaunchAgents/com.hyper-tracker.simulator.plist
rm ~/Library/LaunchAgents/com.hyper-tracker.contrarian.plist
rm ~/Library/LaunchAgents/com.hyper-tracker.simulator.plist
```

## Troubleshooting

### Services won't start
1. Check Python path is correct:
   ```bash
   which python3
   ```
   Should output `/usr/bin/python3` or similar

2. Check for errors in logs:
   ```bash
   cat ../logs/contrarian-stderr.log
   cat ../logs/simulator-stderr.log
   ```

3. Verify plist files exist:
   ```bash
   ls -la ~/Library/LaunchAgents/com.hyper-tracker.*
   ```

### Services keep crashing
1. Check error logs for details
2. Test scripts manually first:
   ```bash
   cd ../contrarian && python3 main.py
   cd ../simulator && python3 main_three_asset.py
   ```
3. Check that all dependencies are installed
4. Verify database files exist and are accessible

### Can't access web dashboards
1. Verify services are running:
   ```bash
   ./status-services.sh
   ```

2. Check if ports are in use:
   ```bash
   lsof -i :5000  # Contrarian dashboard
   lsof -i :8050  # Simulator dashboard
   ```

3. Check logs for startup errors

## Configuration Files

- `com.hyper-tracker.contrarian.plist` - Contrarian service configuration
- `com.hyper-tracker.simulator.plist` - Simulator service configuration

These files define:
- Which Python interpreter to use
- Working directory
- Log file locations
- Auto-restart behavior
- Auto-start on boot behavior

## Best Practices

1. **Test first:** Always test scripts manually before setting up as services
2. **Monitor logs:** Check logs regularly, especially after first setup
3. **Clean shutdown:** Use `./stop-services.sh` before making code changes
4. **Restart after changes:** Run `./restart-services.sh` after updating code

## Sleep Prevention (Built-in)

The `start-services.sh` script automatically prevents your Mac from sleeping using the `caffeinate` command. This ensures your services keep running even when you're away from your Mac.

### What happens:
- **Display can sleep** - screen will turn off to save power
- **Mac will NOT sleep** - CPU and programs keep running
- **Automatic when you start services** - no manual configuration needed
- **Automatic cleanup when you stop services** - Mac can sleep normally again

### Manual sleep control (if needed):
```bash
# Manually prevent sleep
caffeinate -s &

# Stop sleep prevention
killall caffeinate
```

### Note on Power Consumption:
Your Mac will consume more power when sleep is prevented. For long-term testing:
- Keep your Mac plugged in
- Or adjust Energy Saver settings to allow longer idle times before sleep

## Summary

This setup gives you true "set and forget" operation. Start the services, walk away, and they'll keep running until you explicitly stop them. Perfect for long-term performance testing without babysitting your Mac.
