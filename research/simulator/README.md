# Paper Trading Simulator

A live paper trading simulator that executes contrarian trading strategies based on signals from the analyzer.

## Overview

This simulator manages a virtual $100k portfolio, automatically rebalancing positions every 15 minutes based on bad trader positioning signals. It simulates realistic trading conditions including fees, slippage, and mark-to-market P&L calculations.

## Features

- **Real-time Price Data**: Fetches live prices from Hyperliquid API
- **Confidence-Weighted Allocation**: Distributes capital proportionally based on signal confidence
- **Automated Rebalancing**: Adjusts positions every 15 minutes
- **Performance Tracking**: Calculates Sharpe ratio, max drawdown, win rate, and more
- **Web Dashboard**: Real-time monitoring with charts and metrics
- **Complete Trade History**: Logs every execution with fees and slippage

## Architecture

```
simulator/
├── main.py                    # Main entry point
├── simulator.py               # Core simulator orchestration
├── config.py                  # Configuration loader
├── database.py                # Database operations
├── signal_reader.py           # Signal reader
├── position_sizer.py          # Allocation calculator
├── price_fetcher.py           # Hyperliquid API client
├── order_executor.py          # Trade execution simulator
├── portfolio_manager.py       # Position management
├── performance_tracker.py     # Metrics calculator
├── dashboard.py               # Flask web server
├── config.json                # Configuration file
├── simulator.db               # Simulator database
└── templates/
    └── index.html             # Dashboard UI
```

## Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure paths**:
   The default `config.json` is already configured for the correct paths:
   ```json
   {
     "database": {
       "signals_db": "../data/contrarian_signals.db",
       "simulator_db": "../data/simulator.db"
     },
     "logging": {
       "file": "../logs/simulator.log"
     }
   }
   ```
   All paths are relative to the `simulator` directory.

## Usage

### Starting the Simulator

```bash
python simulator/main.py
```

Or from within the simulator directory:
```bash
cd simulator
python main.py
```

The simulator will:
1. Initialize all components
2. Validate Hyperliquid API connectivity
3. Start price update loop (every 5 seconds)
4. Start rebalancing loop (every 15 minutes)
5. Launch web dashboard at http://localhost:5000

### Dashboard

Open http://localhost:5000 in your browser to access the real-time dashboard.

**Dashboard Features:**
- Portfolio value and P&L
- Performance metrics (Sharpe, drawdown, win rate)
- Equity curve chart
- Open positions table
- Position allocation pie chart
- Recent activity log
- Trade history

### Stopping the Simulator

Press `Ctrl+C` to gracefully shut down. The simulator will:
- Save current portfolio state
- Close all database connections
- Stop background threads

## Configuration

Edit `config.json` to customize behavior:

### Portfolio Settings
```json
{
  "portfolio": {
    "starting_capital": 100000,    // Starting USD
    "leverage": 1.0,                // No leverage
    "cash_reserve_pct": 0.0,        // 100% invested
    "max_position_pct": 0.40        // Max 40% per position
  }
}
```

### Strategy Settings
```json
{
  "strategy": {
    "rebalance_interval_seconds": 900,  // 15 minutes
    "min_confidence_threshold": 0.60,   // 60% minimum
    "max_positions": 10,                // Top 10 signals
    "min_trade_size_usd": 1000          // Minimum $1k trades
  }
}
```

### Execution Settings
```json
{
  "execution": {
    "maker_fee": 0.0002,           // 0.02%
    "taker_fee": 0.0005,           // 0.05%
    "slippage_model": {
      "type": "linear",
      "base_bps": 0,
      "size_impact": 0.00001       // Size-based slippage
    }
  }
}
```

## How It Works

### 1. Signal Processing
Every 15 minutes:
- Reads signals from Phase 3 database
- Filters signals with confidence ≥ 60%
- Selects top 10 by confidence (descending)
- Excludes NEUTRAL signals

### 2. Position Sizing
Confidence-weighted allocation:
```python
# Example: 3 signals with confidences [0.85, 0.78, 0.72]
total_confidence = 0.85 + 0.78 + 0.72 = 2.35

# Weights
BTC: 0.85 / 2.35 = 36.2% → $36,200
ETH: 0.78 / 2.35 = 33.2% → $33,200
SOL: 0.72 / 2.35 = 30.6% → $30,600
```

Position constraints:
- Maximum 40% in any single position
- Minimum $1,000 trade size
- 100% of capital allocated (no cash reserve)

### 3. Order Execution
Simulated execution with realistic costs:
```python
# Long order
execution_price = market_price * (1 + slippage + taker_fee)

# Short order
execution_price = market_price * (1 - slippage - taker_fee)

# Slippage model (size-based)
slippage_bps = min(5, position_size_usd / 100000 * 1)
```

### 4. Rebalancing Logic
```
1. Fetch latest signals
2. Calculate target allocations
3. Compare with current positions
4. Execute adjustments:
   - CLOSE positions no longer in top 10
   - OPEN new positions
   - INCREASE/DECREASE existing positions
5. Update database
6. Calculate performance metrics
```

### 5. Performance Metrics

**Sharpe Ratio** (30-day rolling):
```python
sharpe = (mean_daily_return / std_daily_return) * sqrt(365)
```

**Maximum Drawdown**:
```python
max_dd = max((peak - current) / peak)
```

**Win Rate**:
```python
win_rate = winning_trades / total_closed_trades
```

## Database Schema

### Positions Table
Tracks current open positions with real-time P&L.

### Trades Table
Complete trade history including:
- Entry/exit prices
- Fees and slippage
- Realized P&L
- Signal confidence
- Reason for trade

### Portfolio State Table
Snapshots of total equity, P&L, and returns.

### Performance History Table
Time-series of performance metrics.

### Rebalance History Table
Log of all rebalancing events.

## API Endpoints

The dashboard backend exposes these REST endpoints:

- `GET /api/status` - Simulator status
- `GET /api/portfolio` - Portfolio summary
- `GET /api/positions` - Open positions
- `GET /api/trades` - Trade history
- `GET /api/equity_curve` - Equity curve data
- `GET /api/performance` - Performance metrics
- `GET /api/rebalances` - Rebalancing history
- `GET /api/activity` - Recent activity log

## Monitoring

### Logs
All activity is logged to:
- `../logs/simulator.log` - Detailed simulator logs (in main project logs directory)
- Console output - Key events and errors

### Log Levels
- INFO: Normal operations
- WARNING: Non-critical issues (stale prices, etc.)
- ERROR: Failures requiring attention

## Troubleshooting

### API Connection Issues
```
ERROR: Failed to fetch prices from Hyperliquid API
```
**Solution**: Check internet connection and Hyperliquid API status.

### Database Not Found
```
ERROR: [Errno 2] No such file or directory: '../contrarian_signals.db'
```
**Solution**: Update `signals_db` path in `config.json`.

### No Signals Available
```
WARNING: No signals available - closing all positions
```
**Solution**: Ensure Phase 3 is running and generating signals.

### Port Already in Use
```
OSError: [Errno 48] Address already in use
```
**Solution**: Change `dashboard.port` in `config.json` or kill existing process.

## Performance Expectations

### Typical Behavior
- **Rebalancing**: 2-10 adjustments per cycle
- **Position turnover**: Moderate (signals stable for hours)
- **Fees impact**: ~0.05% per trade (taker fees + slippage)
- **Update latency**: Prices update every 5 seconds

### System Requirements
- **CPU**: Minimal (<5% typical)
- **Memory**: ~100-200 MB
- **Network**: Continuous connection required
- **Disk**: <10 MB for database

## Integration with Phase 3

The simulator reads from Phase 3's `contrarian_signals.db`:

```python
# Phase 3 generates signals
contrarian_signals.db:
  - pair: 'BTC'
  - signal: 'SHORT'
  - confidence: 0.85
  - timestamp: '2025-12-03T10:30:00'

# Phase 4 reads and trades on them
simulator.rebalance_portfolio()
  → Opens SHORT BTC position
  → Allocates 36.2% of portfolio
```

## Safety Features

- **Paper trading only** - No real money at risk
- **Automatic state saving** - Recovers from crashes
- **Graceful shutdown** - Ctrl+C saves all data
- **Price staleness detection** - Warns on stale data
- **Position validation** - Prevents invalid trades

## Future Enhancements

Potential improvements:
- [ ] WebSocket for real-time price updates
- [ ] Email/SMS alerts for large P&L swings
- [ ] Backtesting mode with historical data
- [ ] Risk limits (max loss per day, etc.)
- [ ] Multiple strategy support
- [ ] Trade replay and analysis tools

## License

Part of the Hyper-Tracker project.

## Support

For issues or questions:
1. Check logs in `simulator.log`
2. Verify Phase 3 is running and generating signals
3. Test Hyperliquid API connectivity
4. Review configuration in `config.json`
