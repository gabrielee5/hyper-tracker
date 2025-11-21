# Quick Start Guide

Get up and running with Hyperliquid Tracker in 5 minutes!

## Prerequisites

- Python 3.8 or higher installed
- Internet connection
- 5-10 MB of free disk space

## Installation

### Option 1: Quick Start Script (Recommended)

**On macOS/Linux:**
```bash
chmod +x run.sh
./run.sh
```

**On Windows:**
```cmd
run.bat
```

The script will:
1. Create a virtual environment
2. Install all dependencies
3. Create necessary directories
4. Start the tracker

### Option 2: Manual Installation

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure (optional):**
   ```bash
   # Edit .env to customize settings
   nano .env
   ```

4. **Run:**
   ```bash
   cd src
   python main.py
   ```

## Configuration

Edit `.env` to customize your tracking:

### Track Specific Coins
```env
TRACK_ALL_COINS=false
SELECTED_COINS=BTC,ETH,SOL,AVAX
```

### Track All Coins
```env
TRACK_ALL_COINS=true
```

## Accessing the Dashboard

Once running, open your browser to:
```
http://localhost:5000
```

You'll see:
- Real-time statistics
- Active address counts
- Trading volumes
- Recent addresses
- Trades by coin

## Stopping the Tracker

Press `Ctrl+C` in the terminal. The tracker will:
- Flush all pending data
- Save to database
- Display final statistics
- Exit gracefully

## Common Issues

### Port 5000 Already in Use
Change the port in `.env`:
```env
DASHBOARD_PORT=8080
```

### No Trades Appearing
- Wait a few minutes for trades to occur
- Check that selected coins are valid
- Review logs: `tail -f logs/tracker.log`

### Connection Issues
- Verify internet connection
- Check Hyperliquid API status
- Try restarting the tracker

## Next Steps

- View the full [README.md](README.md) for detailed documentation
- Check [logs/tracker.log](logs/tracker.log) for detailed activity
- Export addresses: The database is at `data/addresses.db`
- Explore the API endpoints at `/api/stats`, `/api/addresses`, `/api/top-traders`

## Sample Output

```
================================================================================
HYPERLIQUID TRADER ADDRESS TRACKER
================================================================================
2025-01-21 10:30:15 - INFO - Starting Hyperliquid Tracker
2025-01-21 10:30:16 - INFO - Successfully connected to Hyperliquid
2025-01-21 10:30:16 - INFO - Tracking 4 coins: BTC, ETH, SOL, ARB
2025-01-21 10:30:16 - INFO - Dashboard started at http://0.0.0.0:5000
2025-01-21 10:30:16 - INFO - Tracker started successfully - press Ctrl+C to stop
2025-01-21 10:31:16 - INFO - Flushed batch: 150 new addresses added
2025-01-21 10:32:16 - INFO - Statistics - Trades: 543, Total Addresses: 1250
```

Happy tracking!
