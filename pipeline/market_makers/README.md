# Market Maker Position Monitor

Real-time monitoring and analysis of market maker positions and directional bias on Hyperliquid.

## Overview

This module tracks positions of identified market makers from the analyzer database, calculates their collective directional bias per asset, and provides real-time insights through a web dashboard.

## Features

- **Market Maker Tracking**: Monitors positions of detected market makers
- **Bias Calculation**: Calculates net long/short bias per asset
- **Directional Analysis**: Identifies BULLISH, BEARISH, or NEUTRAL sentiment
- **Real-time Dashboard**: Web interface with auto-refresh
- **Historical Data**: Stores position snapshots and bias history
- **Price Integration**: Fetches current market prices for context

## Installation

```bash
cd market-makers
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Edit `config.json` to customize settings:

- **analyzer_db_path**: Path to analyzer database (must exist)
- **monitoring.fetch_interval_seconds**: How often to fetch new data (default: 60s)
- **monitoring.min_mm_balance**: Minimum account balance to track (default: $50k)
- **bias_analysis.neutral_threshold_percent**: Threshold for neutral bias (default: 10%)
- **dashboard.port**: Web dashboard port (default: 5003)

## Usage

### Start the Monitor

```bash
python main.py
```

The monitor will:
1. Read market makers from the analyzer database
2. Fetch their current positions every 60 seconds
3. Calculate bias metrics
4. Store data in local database
5. Update the web dashboard

### Access the Dashboard

Open your browser to: `http://localhost:5003`

The dashboard displays:
- Total market makers being tracked
- Total position value across all MMs
- Number of assets with MM activity
- Per-asset bias breakdown with visual indicators
- Auto-refreshes every 30 seconds

## How It Works

### Bias Calculation

For each asset, the monitor:

1. **Aggregates Positions**: Sums all MM long and short positions
2. **Calculates Net Bias**: `(Long USD - Short USD) / Total USD × 100`
3. **Determines Direction**:
   - **BULLISH**: Bias > +10%
   - **BEARISH**: Bias < -10%
   - **NEUTRAL**: -10% to +10%
4. **Assesses Strength**:
   - **STRONG**: |Bias| > 30%
   - **MODERATE**: 10% < |Bias| < 30%
   - **WEAK**: |Bias| < 10%

### Example

If for BTC:
- 15 MMs have LONG positions worth $2.5M
- 8 MMs have SHORT positions worth $1.5M

Then:
- Total Value: $4M
- Net Bias: +$1M
- Bias Percentage: +25%
- Direction: **BULLISH MODERATE**

## Data Storage

### Local Database: `data/mm_positions.db`

Three tables:

1. **position_snapshots**: Historical position data (7-day retention)
2. **bias_history**: Calculated bias metrics (30-day retention)
3. **mm_activity**: Market maker activity tracking

### Retention Policy

- Position snapshots: 7 days (configurable)
- Bias history: 30 days (configurable)
- Automatic cleanup on each monitoring cycle

## Dependencies

Requires the **analyzer** module to be running and detecting market makers. The analyzer populates the `market_makers` table which this module reads from.

## Architecture

```
market-makers/
├── main.py                      # Orchestrator
├── config.json                  # Configuration
├── core/
│   ├── config.py               # Config management
│   ├── database.py             # Database operations
│   ├── position_fetcher.py     # Hyperliquid API client
│   ├── bias_analyzer.py        # Bias calculations
│   ├── price_fetcher.py        # Price data
│   └── web_dashboard.py        # Flask server
├── dashboard/
│   └── templates/
│       └── dashboard.html      # Web UI
└── data/
    └── mm_positions.db         # Local database
```

## Logging

Logs are written to: `../logs/mm_monitor.log`

Log levels:
- **INFO**: Normal operation, cycle summaries
- **WARNING**: No data found, API issues
- **ERROR**: Failures, exceptions

## Troubleshooting

### "No active market makers found"

**Cause**: Analyzer database has no market makers detected, or they're all older than 24 hours.

**Solution**:
- Ensure analyzer module is running
- Check `analyzer/data/analyzed_traders.db` has entries in `market_makers` table
- Verify market makers have `last_seen` within 24 hours

### "Analyzer DB not found"

**Cause**: Path to analyzer database is incorrect.

**Solution**: Update `analyzer_db_path` in `config.json` to point to the actual analyzer database file.

### Dashboard shows no data

**Cause**: No positions found for tracked market makers.

**Solution**:
- Wait for next update cycle (60 seconds)
- Check logs for API errors
- Verify market makers are actually trading (have open positions)

### Slow updates

**Cause**: Too many concurrent API requests.

**Solution**: Reduce `concurrency_limit` in config from 10 to 5.

## API Rate Limits

Hyperliquid API allows ~15 calls/second. With default settings:
- 10 concurrent requests
- ~10 seconds to fetch 100 market makers
- Well within 60-second update interval

## Performance

- **Database size**: ~1MB per day of operation
- **Memory usage**: ~50-100MB
- **CPU usage**: Minimal (async I/O bound)
- **Network**: ~100 API calls per minute (depends on MM count)

## Future Enhancements

- Export bias data to CSV
- Telegram notifications for extreme bias shifts
- Historical bias charts
- MM-specific detail modal
- Bias reversal alerts

## License

Part of the hyper-tracker project.
