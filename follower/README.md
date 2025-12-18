# Phase 3: Follower Signal System

Monitor top-performing traders' positions and generate trading signals by following their winning strategies.

IMPORTANT: the folder is a copy of 'contrarian' and then it has been transformed to reflect the bias of good traders. In doing so some things may have not been updated to reflect the change. Double check crucial functions!

## Overview

This system identifies traders with consistently excellent performance (from Phase 2 analysis) and generates **follower trading signals** by taking the same side of their positions.

**Core Concept:** If good traders are heavily positioned LONG on BTC, the system signals LONG BTC (following their expertise).

## Features

- **Real-time Position Monitoring:** Fetches current open positions for all top traders
- **Dual Metrics:** Analyzes both count-based (number of traders) and size-weighted (USD value) positioning
- **Signal Strength Classification:** STRONG, MODERATE, WEAK, or NONE based on consensus level
- **Confidence Scoring:** Accounts for sample size and positioning extremity
- **Beautiful Console Dashboard:** Live-updating terminal UI with Rich library
- **Historical Tracking:** Stores all signals for accuracy validation over time
- **Configurable Thresholds:** Customize what defines "good trader" and signal strength

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Phase 3: Follower Engine                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Query good traders (score >= 90) from Phase 2 DB       │
│                          ↓                                  │
│  2. Fetch current positions from Hyperliquid API           │
│                          ↓                                  │
│  3. Aggregate positions by trading pair (BTC, ETH, etc.)   │
│                          ↓                                  │
│  4. Generate follower signals                              │
│                          ↓                                  │
│  5. Display in dashboard + Store in database               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.8+
- Phase 1 & 2 must be running (trader analysis database required)
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

Edit `follower/config.json` to customize:

```json
{
  "good_trader_score_threshold": 90,    // Score >= 90 = "excellent"
  "min_traders_for_signal": 10,         // Min sample size for signals
  "update_interval_seconds": 1800,      // Refresh every 30 minutes
  "signal_thresholds": {
    "strong": 0.70,                     // 70%+ consensus = STRONG signal
    "moderate": 0.50                    // 50%+ consensus = MODERATE signal
  }
}
```

### 2. Run the Follower Monitor

```bash
# From project root
python3 follower/main.py
```

This starts continuous monitoring with live dashboard updates every 30 minutes.

### 3. Interpret the Dashboard

```
╔══════════════════════════════════════════════════════════════╗
║          FOLLOWER SIGNALS - Good Traders Analysis           ║
║                    Updated: 2025-12-18 14:30:15             ║
╠══════════════════════════════════════════════════════════════╣
║ Total Good Traders Analyzed: 127                             ║
║ Traders with Open Positions: 89                              ║
║ Active Signals: 12 pairs                                     ║
╚══════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────┐
│ BTC                                                🟢 STRONG │
├─────────────────────────────────────────────────────────────┤
│ Signal: LONG BTC                                            │
│ Confidence: 0.82                                            │
│ Good Traders: 45 (76% LONG, 24% SHORT)                     │
│ Reasoning: Top traders are heavily long, follow their lead │
└─────────────────────────────────────────────────────────────┘
```

**Key Indicators:**
- 🟢 **GREEN = STRONG Signal:** 70%+ of good traders agree on direction
- 🟡 **YELLOW = MODERATE Signal:** 50-70% consensus
- ⚪ **NEUTRAL:** No clear consensus (< 50%)

## Signal Logic

The system follows the best traders:

| Good Traders Positioning | Generated Signal | Rationale |
|--------------------------|-----------------|-----------|
| 75% LONG, 25% SHORT | **LONG (STRONG)** | Follow the majority of winners |
| 65% SHORT, 35% LONG | **SHORT (MODERATE)** | Follow the majority of winners |
| 55% LONG, 45% SHORT | **LONG (WEAK)** | Slight consensus to follow |
| 50% LONG, 50% SHORT | **NEUTRAL** | No clear direction |

## Database Schema

Signals are stored in `data/follower_signals.db`:

### `follower_signals` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `timestamp` | TIMESTAMP | When signal was generated |
| `coin` | TEXT | Trading pair (BTC, ETH, etc.) |
| `signal_direction` | TEXT | LONG, SHORT, or NEUTRAL |
| `signal_strength` | TEXT | STRONG, MODERATE, WEAK, NONE |
| `good_traders_total` | INTEGER | Number of top traders analyzed |
| `long_count` | INTEGER | Number of traders LONG |
| `short_count` | INTEGER | Number of traders SHORT |
| `long_percentage` | REAL | % of traders LONG (0-100) |
| `short_percentage` | REAL | % of traders SHORT (0-100) |
| `confidence_score` | REAL | Signal confidence (0.0 to 1.0) |

### `position_snapshot` Table

Stores raw position data for all monitored good traders at each update interval.

## Configuration Reference

All settings in `config.json`:

```json
{
  "good_trader_score_threshold": 90,
  "min_traders_for_signal": 10,
  "signal_thresholds": {
    "strong": 0.70,
    "moderate": 0.50
  },
  "update_interval_seconds": 1800,
  "api": {
    "base_url": "https://api.hyperliquid.xyz",
    "rate_limit_calls": 15,
    "rate_limit_period": 1.0,
    "timeout": 10,
    "max_retries": 3,
    "concurrency_limit": 10
  },
  "database": {
    "phase2_path": "../data/analyzed_traders.db",
    "follower_path": "../data/follower_signals.db"
  },
  "dashboard": {
    "refresh_rate": 5,
    "show_size_weighted": true,
    "top_signals_limit": 15,
    "enable_colors": true,
    "priority_coins": ["BTC", "ETH", "SOL"]
  }
}
```

## Comparison with Contrarian Strategy

| Aspect | Follower | Contrarian |
|--------|----------|------------|
| **Target Traders** | Top performers (score >= 90) | Poor performers (score <= 10) |
| **Signal Logic** | Follow their positions | Opposite their positions |
| **Theory** | Smart money knows best | Dumb money is consistently wrong |
| **Risk Profile** | Lower (following winners) | Higher (betting against losers) |

## Troubleshooting

### No Signals Generated

```
Warning: Only 3 good traders found. Minimum 10 required for signals.
```

**Solution:** Lower `good_trader_score_threshold` in config.json to include more traders, or wait for Phase 2 to analyze more trader data.

### Empty Dashboard

**Possible causes:**
1. No good traders have open positions currently
2. Phase 2 database not found
3. Hyperliquid API rate limit hit

**Check logs:**
```bash
tail -f ../logs/follower.log
```

### API Rate Limiting

If you see rate limit errors, adjust in config:
```json
"api": {
  "rate_limit_calls": 10,  // Reduce from 15
  "concurrency_limit": 5   // Reduce from 10
}
```

## Web Dashboard

A web dashboard is automatically started on port 5000:

```
http://127.0.0.1:5000
```

View signals in your browser with real-time updates.

## Data Analysis

Query historical signals with SQL:

```bash
sqlite3 ../data/follower_signals.db
```

```sql
-- Most confident signals in last 24 hours
SELECT coin, signal_direction, confidence_score, good_traders_total, timestamp
FROM follower_signals
WHERE timestamp > datetime('now', '-1 day')
AND signal_strength IN ('STRONG', 'MODERATE')
ORDER BY confidence_score DESC
LIMIT 10;

-- Track BTC signal history
SELECT
  timestamp,
  signal_direction,
  signal_strength,
  long_percentage,
  short_percentage,
  confidence_score
FROM follower_signals
WHERE coin = 'BTC'
ORDER BY timestamp DESC
LIMIT 20;
```

## Performance Notes

- **Memory usage:** ~50-100 MB
- **API calls:** ~1 per trader every 30 minutes
- **Database size:** Grows ~1 MB per day with default settings
- **CPU usage:** Minimal (< 5% during updates)

## Theory: Why Follow Good Traders?

The follower strategy is based on several principles:

1. **Information Advantage:** Successful traders often have better information and analysis
2. **Skill Persistence:** Good traders tend to maintain their edge over time
3. **Trend Following:** Winners are positioned correctly for current market conditions
4. **Risk Management:** Good traders use better position sizing and stop losses

## Next Steps

1. **Backtest signals:** Compare historical signals to actual price movements
2. **Combine strategies:** Use both follower AND contrarian for diversification
3. **Adjust thresholds:** Fine-tune based on your risk tolerance
4. **Add filters:** Consider market conditions, volatility, etc.

## License

MIT
