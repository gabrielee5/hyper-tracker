# Phase 3: Contrarian Signal System

Monitor bad traders' positions and generate inverse trading signals to profit from their losing strategies.

## Overview

This system identifies traders with consistently poor performance (from Phase 2 analysis) and generates **contrarian trading signals** by taking the opposite side of their positions.

**Core Concept:** If bad traders are heavily positioned LONG on BTC, the system signals SHORT BTC (and vice versa).

## Features

- **Real-time Position Monitoring:** Fetches current open positions for all bad traders
- **Dual Metrics:** Analyzes both count-based (number of traders) and size-weighted (USD value) positioning
- **Signal Strength Classification:** STRONG, MODERATE, WEAK, or NONE based on consensus level
- **Confidence Scoring:** Accounts for sample size and positioning extremity
- **Beautiful Console Dashboard:** Live-updating terminal UI with Rich library
- **Historical Tracking:** Stores all signals for accuracy validation over time
- **Configurable Thresholds:** Customize what defines "bad trader" and signal strength

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Phase 3: Contrarian Engine                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Query bad traders (score < 5) from Phase 2 DB          │
│                          ↓                                  │
│  2. Fetch current positions from Hyperliquid API           │
│                          ↓                                  │
│  3. Aggregate positions by trading pair (BTC, ETH, etc.)   │
│                          ↓                                  │
│  4. Generate contrarian signals                            │
│                          ↓                                  │
│  5. Display in dashboard + Store in database               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.8+
- Phase 1 & 2 must be running (bad traders database required)
- Virtual environment activated

### Install Dependencies

```bash
# From project root
source venv/bin/activate
pip install rich aiolimiter
```

Dependencies are already in `requirements.txt` for Phase 2.

## Quick Start

### 1. Configure Settings (Optional)

Edit `contrarian/config.json` to customize:

```json
{
  "bad_trader_score_threshold": 5,      // Score <= 5 = "very bad"
  "min_traders_for_signal": 10,         // Min sample size for signals
  "update_interval_seconds": 90,        // Refresh every 90 seconds
  "signal_thresholds": {
    "strong": 0.70,                     // 70%+ consensus = STRONG signal
    "moderate": 0.60                    // 60%+ consensus = MODERATE signal
  }
}
```

### 2. Run the Contrarian Monitor

```bash
# From project root
python3 contrarian/main.py
```

This starts continuous monitoring with live dashboard updates every 90 seconds.

### 3. Interpret the Dashboard

```
╔══════════════════════════════════════════════════════════════╗
║          CONTRARIAN SIGNALS - Bad Traders Analysis          ║
║                    Updated: 2024-12-02 14:30:15             ║
╠══════════════════════════════════════════════════════════════╣
║ Total Bad Traders Analyzed: 277                              ║
║ Traders with Open Positions: 142                             ║
║ Active Signals: 8 pairs                                      ║
╚══════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────┐
│ BTC                                                🔴 STRONG │
├─────────────────────────────────────────────────────────────┤
│ Bad Traders: 45 positions                                   │
│ Count-Based:   L:82%(37) S:18%(8)                          │
│ Size-Weighted: L:83%($890K) S:17%($180K)                    │
│                                                             │
│ 🎯 CONTRARIAN SIGNAL: SHORT BTC                             │
│    Confidence: 0.89 (high consensus, large sample)          │
└─────────────────────────────────────────────────────────────┘
```

**Reading the Signal:**
- **BTC 🔴 STRONG SHORT:** 82% of bad traders are LONG → Signal says go SHORT
- **Confidence 0.89:** Very high confidence (0.0-1.0 scale)
- **Count-Based:** 37 traders long, 8 short
- **Size-Weighted:** $890K in long positions, $180K in short positions

## Signal Logic

### Signal Generation

```
If 70%+ of bad traders are LONG  → STRONG SHORT signal
If 60-70% are LONG               → MODERATE SHORT signal

If 70%+ of bad traders are SHORT → STRONG LONG signal
If 60-70% are SHORT              → MODERATE LONG signal

If 40-60% either way             → NEUTRAL (no signal)
```

### Confidence Score Calculation

```python
# 1. Positioning extremity (70% = 0.4, 90% = 0.8)
imbalance = abs(long_percentage - 50%) / 50%

# 2. Sample size factor (scales from min to 3x min)
sample_factor = min(1.0, total_traders / (min_traders * 3))

# 3. Combined (weighted 70% imbalance, 30% sample size)
confidence = (imbalance * 0.7) + (sample_factor * 0.3)
```

**Higher confidence when:**
- More extreme positioning (80%+ vs 60%)
- Larger sample size (30+ traders vs 10)

### Minimum Requirements

A signal is only generated if:
1. **Sample size:** ≥10 bad traders have positions in that pair (configurable)
2. **Consensus:** ≥60% positioned on one side (configurable)

## Module Structure

```
contrarian/
├── config.json                # Configuration settings
├── main.py                    # Main orchestrator
├── test_contrarian.py         # Test suite
├── README.md                  # This file
│
├── core/
│   ├── config.py              # Config management
│   ├── database.py            # Phase 2 reader + contrarian DB
│   ├── position_fetcher.py    # Hyperliquid API client
│   ├── aggregator.py          # Position aggregation
│   ├── signal_generator.py    # Signal generation logic
│   └── dashboard.py           # Rich-based console UI
│
├── data/
│   └── contrarian_signals.db  # Historical signals (auto-created)
│
└── logs/
    └── contrarian.log         # Application logs
```

## Database Schema

### contrarian_signals table

Stores all generated signals for historical analysis:

```sql
CREATE TABLE contrarian_signals (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP,
    coin TEXT,
    signal_direction TEXT,     -- 'LONG', 'SHORT', 'NEUTRAL'
    signal_strength TEXT,       -- 'STRONG', 'MODERATE', 'WEAK', 'NONE'

    -- Count-based metrics
    bad_traders_total INTEGER,
    long_count INTEGER,
    short_count INTEGER,
    long_percentage REAL,
    short_percentage REAL,

    -- Size-weighted metrics
    long_usd_value REAL,
    short_usd_value REAL,
    long_usd_percentage REAL,
    short_usd_percentage REAL,

    confidence_score REAL
);
```

### position_snapshot table

Stores individual trader positions for analysis:

```sql
CREATE TABLE position_snapshot (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP,
    address TEXT,
    coin TEXT,
    side TEXT,              -- 'LONG' or 'SHORT'
    size REAL,
    position_value_usd REAL,
    entry_price REAL,
    leverage_value REAL,
    unrealized_pnl REAL
);
```

## API Usage

### Hyperliquid API

The system uses the Hyperliquid Info API `clearinghouseState` endpoint:

```python
# Endpoint: POST https://api.hyperliquid.xyz/info
# Payload:
{
    "type": "clearinghouseState",
    "user": "0x..."  # Ethereum address
}

# Response includes:
{
    "assetPositions": [
        {
            "coin": "BTC",
            "szi": "0.5",        # Positive = long, negative = short
            "entryPx": "45000",
            "positionValue": "22500",
            "unrealizedPnl": "500",
            "leverage": {"type": "cross", "value": 5}
        }
    ],
    "marginSummary": {...},
    "withdrawable": "10000"
}
```

**Rate Limiting:**
- Default: 15 calls/second
- Respects 429 errors with 30s cooldown
- Concurrent request limit: 10

## Testing

### Run Test Suite

```bash
python3 contrarian/test_contrarian.py
```

Tests all components:
1. Phase 2 database reader
2. Position fetching from Hyperliquid
3. Position aggregation
4. Signal generation
5. Dashboard rendering
6. Database storage

### Sample Output

```
TEST 1: Phase 2 Database Reader
Found 277 bad traders (score <= 5)

TEST 2: Position Fetcher
Found 142 positions from 67 traders

TEST 3: Position Aggregation
Aggregated 8 coins

TEST 4: Signal Generation
Generated 5 signals (3 actionable)

TEST 5: Dashboard Display
[Displays live dashboard]

✅ ALL TESTS COMPLETED SUCCESSFULLY
```

## Configuration Reference

### config.json Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `bad_trader_score_threshold` | 5 | Max score for "bad trader" (0-100) |
| `min_traders_for_signal` | 10 | Minimum traders required for signal |
| `signal_thresholds.strong` | 0.70 | Strong signal threshold (70%) |
| `signal_thresholds.moderate` | 0.60 | Moderate signal threshold (60%) |
| `update_interval_seconds` | 90 | Refresh interval for monitoring |
| `api.rate_limit_calls` | 15 | Max API calls per second |
| `api.concurrency_limit` | 10 | Max concurrent API requests |
| `dashboard.show_size_weighted` | true | Show both count & size metrics |
| `dashboard.top_signals_limit` | 15 | Max signals to display |

### Adjusting Sensitivity

**More aggressive (more signals):**
```json
{
  "bad_trader_score_threshold": 10,    // Include more traders
  "min_traders_for_signal": 5,         // Lower sample size
  "signal_thresholds": {
    "strong": 0.65,                    // Lower threshold
    "moderate": 0.55
  }
}
```

**More conservative (fewer, higher quality signals):**
```json
{
  "bad_trader_score_threshold": 3,     // Only worst traders
  "min_traders_for_signal": 20,        // Higher sample size
  "signal_thresholds": {
    "strong": 0.80,                    // Higher threshold
    "moderate": 0.70
  }
}
```

## Troubleshooting

### No signals generated

**Cause:** Not enough bad traders have open positions

**This is normal behavior!** Bad traders aren't always actively trading. Out of 277 bad traders, only 20-50 may have open positions at any given time.

**Check current status:**
```bash
python3 contrarian/check_positions.py
```

**Solutions if needed:**
- Lower `min_traders_for_signal` in config (try 5 instead of 10)
- Increase `bad_trader_score_threshold` to include more traders (try 10 instead of 5)
- Wait for bad traders to open positions (system monitors continuously)
- Check if Phase 2 database has recent analysis

### API rate limit errors

**Cause:** Too many concurrent requests

**Solution:**
- Reduce `api.concurrency_limit` in config
- Increase `update_interval_seconds`
- Check `api.rate_limit_calls` setting

### Database not found

**Cause:** Phase 2 database path incorrect

**Solution:**
- Verify `database.phase2_path` in config.json
- Ensure Phase 2 analyzer has run and created `analyzed_traders.db`

### No bad traders found

**Cause:** Phase 2 hasn't analyzed enough traders

**Solution:**
- Run Phase 2 analyzer: `python3 analyzer/main.py`
- Wait for analysis to complete (analyzes traders in background)
- Check Phase 2 database: `sqlite3 analyzer/data/analyzed_traders.db "SELECT COUNT(*) FROM scored_traders WHERE score <= 5"`

## Advanced Usage

### Query Historical Signals

```bash
# Open database
sqlite3 contrarian/data/contrarian_signals.db

# Get all BTC signals from last 24 hours
SELECT timestamp, signal_direction, signal_strength, confidence_score
FROM contrarian_signals
WHERE coin = 'BTC'
  AND timestamp > datetime('now', '-1 day')
ORDER BY timestamp DESC;

# Calculate signal accuracy (if you tracked outcomes)
SELECT
    signal_direction,
    COUNT(*) as total_signals,
    AVG(confidence_score) as avg_confidence
FROM contrarian_signals
WHERE signal_strength IN ('STRONG', 'MODERATE')
GROUP BY signal_direction;
```

### Programmatic Access

```python
import asyncio
from contrarian.main import ContrarianEngine
from contrarian.core.config import ConrarianConfig

async def get_current_signals():
    config = ConrarianConfig()
    engine = ContrarianEngine(config)

    await engine.initialize()
    await engine.run_once()  # Run one cycle

    return engine.last_signals

# Get signals
signals = asyncio.run(get_current_signals())

# Filter actionable signals
actionable = [
    s for s in signals
    if s['signal_strength'] in ['STRONG', 'MODERATE']
    and s['confidence_score'] >= 0.60
]

for signal in actionable:
    print(f"{signal['coin']}: {signal['signal_direction']} "
          f"(confidence: {signal['confidence_score']:.2f})")
```

## Integration with Trading Bots

The system is designed to output clean signals that can be consumed by trading bots:

```python
# Example: Send STRONG signals to trading bot
async def send_to_trading_bot(signals):
    strong_signals = [
        s for s in signals
        if s['signal_strength'] == 'STRONG'
        and s['confidence_score'] >= 0.75
    ]

    for signal in strong_signals:
        await trading_bot.place_order(
            symbol=f"{signal['coin']}-USD",
            side=signal['signal_direction'],
            size=calculate_position_size(signal['confidence_score'])
        )
```

## Performance Metrics

### Typical Performance

- **277 bad traders:** ~90 seconds to fetch and analyze all positions
- **Memory usage:** ~50MB
- **API calls:** ~280 calls per cycle (1 per trader + metadata)
- **Dashboard refresh:** <1 second

### Scalability

The system can handle:
- **Traders:** Up to 1000 bad traders (limited by API rate limits)
- **Update frequency:** Minimum 60 seconds (to respect API limits)
- **Historical data:** Unlimited (SQLite database)

## Roadmap / Future Enhancements

Potential improvements for Phase 3.5:

1. **Signal Validation:**
   - Track actual price movements after signals
   - Calculate signal win rate over time
   - Backtest historical signals

2. **JSON API:**
   - REST API for bot integration
   - WebSocket for real-time updates
   - Web dashboard (HTML/JavaScript)

3. **Advanced Analytics:**
   - Correlation analysis between signals and outcomes
   - Risk metrics (position concentration, leverage)
   - Alert system (Discord/Telegram notifications)

4. **Machine Learning:**
   - Weighted averaging (give more weight to worse traders)
   - Pattern recognition (detect common bad trader mistakes)
   - Predictive modeling (forecast signal accuracy)

## Support

For issues or questions:

1. Check logs: `cat contrarian.log`
2. Run test suite: `python3 contrarian/test_contrarian.py`
3. Verify Phase 2 is running: `python3 analyzer/main.py`
4. Review configuration: `cat contrarian/config.json`

## License

Part of the Hyperliquid Trader Tracker project.

---

**⚠️ Disclaimer:** This system is for informational purposes only. Past performance of bad traders does not guarantee future results. Always do your own research and risk management before trading.
