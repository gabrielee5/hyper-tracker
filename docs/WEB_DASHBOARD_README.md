# Web Dashboard for Contrarian Signals

## Overview

The contrarian program now includes a **web-based dashboard** alongside the existing terminal interface. Both dashboards display the same information but in different formats.

## What's New

### Web Dashboard Features
- **Real-time updates**: Auto-refreshes every 5 seconds
- **Beautiful UI**: Modern, responsive design with gradient backgrounds
- **Visual indicators**: Color-coded signals and position bars
- **Priority coins**: Highlighted watchlist coins (BTC, ETH, etc.)
- **Statistics overview**: Total bad traders, positions, and active signals
- **Accessible**: View from any browser on your network

### Terminal Dashboard
- The original terminal dashboard still works exactly as before
- Both dashboards show the same data simultaneously
- Terminal output continues to provide Rich console interface

## How to Use

### Starting the Dashboard

Simply run the contrarian program as usual:

```bash
./run_contrarian.sh
```

Or directly:

```bash
python3 contrarian/main.py
```

The program will:
1. Start the web server on http://127.0.0.1:5000
2. Continue showing terminal output as usual
3. Update both dashboards simultaneously

### Accessing the Web Dashboard

Once the program is running:

1. Open your web browser
2. Navigate to: **http://127.0.0.1:5000**
3. The dashboard will load and auto-refresh every 5 seconds

### What You'll See

#### Header Section
- **Total Bad Traders**: Number of traders being monitored
- **With Open Positions**: How many currently have positions
- **Active Signals**: Number of generated trading signals
- **Last Updated**: Timestamp of most recent data

#### Signals Table
- **Coin**: The cryptocurrency symbol
- **Signal**: Trading recommendation (LONG/SHORT) with strength indicator
- **Strength**: STRONG, MODERATE, or WEAK
- **Confidence**: Percentage confidence score
- **Traders**: Number of bad traders with positions
- **Count-Based Positioning**: Visual bar showing long vs short by trader count
- **Size-Weighted Positioning**: Visual bar showing long vs short by USD value

#### Visual Indicators
- 🔴 **Red circle**: Strong SHORT signal
- 🟠 **Orange circle**: Moderate SHORT signal
- 🟢 **Green circle**: Strong LONG signal
- 🟡 **Yellow circle**: Moderate LONG signal
- **Yellow badge**: Priority coin from watchlist

## Testing the Dashboard

You can test the web dashboard independently with sample data:

```bash
python3 contrarian/test_web_dashboard.py
```

This will:
- Load sample signals
- Start the web server
- Allow you to view the dashboard without running the full system

## File Structure

```
contrarian/
├── core/
│   ├── web_dashboard.py       # Flask web server and API
│   └── dashboard.py            # Terminal dashboard (unchanged)
├── templates/
│   └── dashboard.html          # Web UI HTML/CSS/JavaScript
├── main.py                     # Updated to support both dashboards
├── main_terminal_backup.py    # Backup of original version
└── test_web_dashboard.py      # Test script
```

## Backup

The original terminal-only version has been backed up to:
- `contrarian/main_terminal_backup.py`

You can revert to terminal-only mode by copying this file back:

```bash
cp contrarian/main_terminal_backup.py contrarian/main.py
```

## Technical Details

### Dependencies
- **Flask**: Web framework
- **flask-cors**: CORS support
- All existing dependencies remain the same

### API Endpoints
- `GET /`: Serves the dashboard HTML
- `GET /api/signals`: Returns current signals and statistics (JSON)
- `GET /api/health`: Health check endpoint

### Configuration
- Web server runs on `127.0.0.1:5000` by default
- Can be customized in `web_dashboard.py` if needed
- Auto-refresh interval is 5 seconds (configurable in HTML)

## Benefits

### Web Dashboard Advantages
- View from multiple devices/screens
- Keep monitoring while doing other work
- Shareable with team members on same network
- Better for long-term monitoring
- Easier to take screenshots

### Terminal Dashboard Advantages
- No browser required
- Works in SSH sessions
- Lightweight
- Familiar for CLI users
- Better for quick checks

## Troubleshooting

### Port Already in Use
If port 5000 is already in use, you'll see an error. Edit `contrarian/core/web_dashboard.py` and change the port:

```python
def __init__(
    self,
    host: str = '127.0.0.1',
    port: int = 5000,  # Change this to 5001, 5002, etc.
    ...
)
```

### Web Dashboard Not Updating
- Check that the contrarian program is running
- Refresh your browser (Ctrl+R or Cmd+R)
- Check browser console for errors (F12)
- Verify API endpoint: http://127.0.0.1:5000/api/signals

### Can't Access from Another Computer
By default, the dashboard only listens on `127.0.0.1` (localhost). To access from other computers:

1. Edit `contrarian/core/web_dashboard.py`
2. Change `host: str = '127.0.0.1'` to `host: str = '0.0.0.0'`
3. Access using your computer's IP address: `http://192.168.x.x:5000`

**Security Warning**: Only expose to trusted networks!

## Support

For issues or questions:
1. Check the terminal output for error messages
2. Check `logs/contrarian.log` for details
3. Verify all dependencies are installed
4. Try the test script first: `python3 contrarian/test_web_dashboard.py`
