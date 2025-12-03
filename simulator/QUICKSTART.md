# Quick Start Guide - Paper Trading Simulator

## Prerequisites
- Python 3.8+
- Contrarian signals database (`../data/contrarian_signals.db`)
- Internet connection (for Hyperliquid API)

## Installation

1. **Navigate to the simulator directory:**
   ```bash
   cd simulator
   ```

2. **Install dependencies** (if not already installed):
   ```bash
   pip install -r requirements.txt
   ```

## Running the Simulator

### Start the simulator:
```bash
python main.py
```

You should see:
```
================================================================================
PAPER TRADING SIMULATOR - Phase 4
================================================================================

✓ Configuration loaded
  - Starting capital: $100,000.00
  - Rebalance interval: 900s
  - Min confidence: 60%
  - Max positions: 10

Initializing simulator...
✓ Simulator initialized

Starting web dashboard...
✓ Dashboard available at: http://localhost:5000

Starting trading simulator...

================================================================================
SIMULATOR IS NOW RUNNING
================================================================================

Dashboard: http://localhost:5000
Press Ctrl+C to stop
```

### Access the Dashboard

Open your web browser and navigate to:
```
http://localhost:5000
```

The dashboard shows:
- **Portfolio Value**: Current equity and P&L
- **Performance Metrics**: Sharpe ratio, max drawdown, win rate
- **Equity Curve**: Real-time portfolio value chart
- **Open Positions**: All current trades
- **Position Allocation**: Pie chart of holdings
- **Recent Activity**: Trade log
- **Trade History**: Complete execution record

### What Happens Next

The simulator will:

1. **Immediately** (within 5 seconds):
   - Fetch latest prices from Hyperliquid
   - Read signals from Phase 3 database
   - Execute initial rebalancing
   - Open positions based on top signals

2. **Every 5 seconds**:
   - Update all position prices
   - Recalculate portfolio value and P&L
   - Refresh dashboard data

3. **Every 15 minutes**:
   - Re-read signals from Phase 3
   - Calculate new target allocations
   - Rebalance portfolio (open/close/adjust positions)
   - Save performance snapshot

## Stopping the Simulator

Press `Ctrl+C` to gracefully shut down. The simulator will:
- Save final portfolio state
- Close database connections
- Stop all background threads

## Monitoring Performance

### Logs
Check the log file for detailed activity:
```bash
tail -f ../logs/simulator.log
```

Or from the main project directory:
```bash
tail -f logs/simulator.log
```

### Database
Query the simulator database directly:
```bash
sqlite3 ../data/simulator.db "SELECT * FROM positions;"
sqlite3 ../data/simulator.db "SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;"
```

Or from the main project directory:
```bash
sqlite3 data/simulator.db "SELECT * FROM positions;"
sqlite3 data/simulator.db "SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;"
```

### API Endpoints
Access data programmatically:
```bash
# Portfolio summary
curl http://localhost:5000/api/portfolio | jq

# Open positions
curl http://localhost:5000/api/positions | jq

# Recent trades
curl http://localhost:5000/api/trades | jq
```

## Expected First Run Behavior

### Initial State
- Starting Capital: $100,000
- Open Positions: 0
- Total P&L: $0.00

### First Rebalance (within 5-10 seconds)
The simulator will:
1. Fetch 10 signals with confidence ≥ 60%
2. Calculate confidence-weighted allocations
3. Open 10 positions (or fewer if < 10 qualify)
4. Log all trades

Example first rebalance:
```
Retrieved 10 qualifying signals
Calculated allocations for 10 positions
Total capital: $100,000.00
Total allocated: $100,000.00 (100.0%)

Opened LONG position in PENGU: $10,500.00 @ $0.0423
Opened LONG position in ARB: $9,800.00 @ $1.21
Opened LONG position in POL: $9,600.00 @ $0.89
...
Rebalancing complete: 10 adjustments
```

### After 15 Minutes
- Portfolio value will reflect price changes
- Simulator will rebalance if signals changed
- Performance metrics will start calculating

## Troubleshooting

### "No signals available"
**Problem**: Phase 3 database is empty or not being updated
**Solution**: Ensure Phase 3 analyzer is running and generating signals

### "Price not available for BTC"
**Problem**: Hyperliquid API connection issue or coin name mismatch
**Solution**: Check internet connection and verify coin names match Hyperliquid format

### "Port 5000 already in use"
**Problem**: Another application is using port 5000
**Solution**: Edit `config.json` and change `dashboard.port` to another port (e.g., 5001)

### "Database locked"
**Problem**: Multiple processes accessing same database
**Solution**: Stop all instances and run only one simulator at a time

## Configuration Tips

### Faster Rebalancing (for testing)
Edit `config.json`:
```json
{
  "strategy": {
    "rebalance_interval_seconds": 60  // Rebalance every minute
  }
}
```

### Higher Confidence Threshold
Only trade very strong signals:
```json
{
  "strategy": {
    "min_confidence_threshold": 0.80  // 80% minimum
  }
}
```

### Smaller Portfolio
Test with less capital:
```json
{
  "portfolio": {
    "starting_capital": 10000  // $10k instead of $100k
  }
}
```

## Live Trading Checklist

Before running for extended periods:

- [ ] Phase 3 is running and generating fresh signals
- [ ] Internet connection is stable
- [ ] Sufficient disk space for database growth
- [ ] Log monitoring is set up
- [ ] Dashboard is accessible
- [ ] Configuration is validated

## Performance Expectations

### Normal Operation
- CPU: < 5% average
- Memory: ~100-200 MB
- Network: Minimal (API calls every 5 seconds)
- Rebalancing: 2-10 position adjustments per cycle

### First 30 Days
- Sharpe ratio: Not calculated (insufficient data)
- Max drawdown: Tracks peak-to-trough decline
- Win rate: Calculated from closed trades only

### After 30 Days
- All metrics fully operational
- Sharpe ratio uses rolling 30-day window
- Historical equity curve shows full performance

## Next Steps

1. **Monitor for 24 hours** - Ensure stable operation
2. **Review logs** - Check for any errors or warnings
3. **Analyze performance** - Use dashboard to evaluate strategy
4. **Adjust configuration** - Tune parameters based on results
5. **Scale up** - Run continuously for long-term testing

## Support

For issues:
1. Check `../logs/simulator.log` for errors
2. Verify Phase 3 is running
3. Test Hyperliquid API: `curl https://api.hyperliquid.xyz/info`
4. Review configuration in `config.json`
5. Consult README.md for detailed documentation

Happy simulated trading!
