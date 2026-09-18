# Quick Start Guide

Get the Market Maker Position Monitor up and running in 5 minutes.

## Prerequisites

1. **Analyzer module running**: Must have market makers in `analyzer/data/analyzed_traders.db`
2. **Python 3.9+** installed
3. **Virtual environment** (recommended)

## Installation

```bash
# Navigate to market-makers directory
cd /path/to/hyper-tracker/market-makers

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

The default `config.json` should work out of the box if your analyzer database is at the standard location.

**Optional**: Edit `config.json` if needed:

```json
{
  "analyzer_db_path": "../analyzer/data/analyzed_traders.db",  // ← Check this path
  "dashboard": {
    "port": 5003  // ← Change if port conflicts
  }
}
```

## Run

```bash
python main.py
```

You should see:

```
================================================================================
Market Maker Position Monitor
================================================================================
Min MM balance: $50,000
Max MM age: 24.0h
Fetch interval: 60s
Neutral threshold: ±10.0%
Strong threshold: ±30.0%
================================================================================
Found 47 market makers in analyzer database
================================================================================
📊 Web Dashboard: http://localhost:5003
================================================================================

Starting monitoring cycle...
```

## Access Dashboard

Open your browser to: **http://localhost:5003**

## What You'll See

### Dashboard Header
- **Total Market Makers**: All MMs in database
- **Total Position Value**: Combined USD value of all positions
- **Assets Tracked**: Number of unique coins with MM positions
- **Active MMs (24h)**: MMs with current open positions

### Asset Bias Table

For each coin:
- **ASSET**: Coin symbol + current price
- **MMS**: Number of market makers trading it
- **LONG VALUE**: Total long position value
- **SHORT VALUE**: Total short position value
- **NET BIAS**: Difference (long - short)
- **BIAS %**: Percentage bias
- **DIRECTION**: BULLISH/BEARISH/NEUTRAL badge with strength
- **VISUAL**: Bar chart showing long/short ratio

### Example

```
┌─────────────────────────────────────────────────────────────┐
│ BTC              | 28 | $4.2M | $1.8M | +$2.4M | +40% | ... │
│ $95,432.50       |    |       |       |        |      |     │
├─────────────────────────────────────────────────────────────┤
│ DIRECTION: [BULLISH MODERATE]                               │
│ VISUAL: [████████████░░░░░░░░] 67% LONG | 33% SHORT        │
└─────────────────────────────────────────────────────────────┘
```

## Understanding Bias

### Direction

- **BULLISH**: More MMs are long (bias > +10%)
- **BEARISH**: More MMs are short (bias < -10%)
- **NEUTRAL**: Balanced positions (-10% to +10%)

### Strength

- **STRONG**: Very one-sided (|bias| > 30%)
- **MODERATE**: Clear direction (10-30%)
- **WEAK**: Slight bias (<10%)

## Monitoring Cycle

Every 60 seconds, the monitor:

1. ✓ Reads market makers from analyzer DB
2. ✓ Fetches their positions from Hyperliquid
3. ✓ Calculates bias per asset
4. ✓ Fetches current prices
5. ✓ Saves to local database
6. ✓ Updates dashboard

## Logs

Watch the terminal for updates:

```
2026-01-05 14:30:00 - INFO - Found 47 active market makers
2026-01-05 14:30:05 - INFO - Found 342 positions from 42 active market makers
2026-01-05 14:30:06 - INFO - Calculated bias for 15 coins
2026-01-05 14:30:07 - INFO - ✓ Cycle completed successfully
```

Full logs: `../logs/mm_monitor.log`

## Common Issues

### "No active market makers found"

→ Wait for analyzer to detect market makers, or check `max_mm_age_hours` in config

### "Analyzer DB not found"

→ Verify `analyzer_db_path` points to correct location

### Port already in use

→ Change `dashboard.port` in config.json to 5004 or another free port

## Stopping the Monitor

Press **Ctrl+C** in the terminal. The monitor will:
- Stop gracefully
- Close API connections
- Clean up old data
- Exit

## Next Steps

- Leave it running 24/7 to build historical data
- Check dashboard periodically for MM sentiment shifts
- Use bias data to inform trading decisions (contrarian or following)
- Export data for analysis (future feature)

## Tips

1. **Contrarian Strategy**: When 90%+ MMs are on one side, consider the opposite
2. **Trend Following**: Strong consistent bias may indicate a trend
3. **Neutral Assets**: May indicate uncertainty or balanced market
4. **Monitor Changes**: Sudden bias flips can signal reversals

## Support

- Check `README.md` for detailed documentation
- Review implementation plan: `../market-maker-monitor-implementation-plan.md`
- Check logs for error messages
- Verify analyzer module is running properly

Happy monitoring! 📊
