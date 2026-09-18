# Phase 3 Contrarian Signals - Quick Start Guide

Get up and running with contrarian signals in 5 minutes.

## Prerequisites

✅ Phase 1 (Trade Tracker) running
✅ Phase 2 (Trader Analyzer) has analyzed traders (check: `sqlite3 analyzer/data/analyzed_traders.db "SELECT COUNT(*) FROM scored_traders WHERE score <= 5"`)
✅ Python 3.8+ and virtual environment activated

## Step 1: Install Dependencies (30 seconds)

```bash
# From project root
source venv/bin/activate
pip install rich aiolimiter
```

## Step 2: Run the Contrarian Monitor (Instant)

```bash
# From project root
python3 contrarian/main.py
```

That's it! You should see:

```
================================================================================
Phase 3: Contrarian Signal System
================================================================================
Bad trader threshold: score <= 5
Min traders for signal: 10
Update interval: 90s
================================================================================

2024-12-02 14:30:15 - INFO - Found 277 bad traders in Phase 2 database
2024-12-02 14:30:15 - INFO - Fetching positions from Hyperliquid...
```

## Step 3: Interpret Your First Signal

When the dashboard appears:

```
╔══════════════════════════════════════════════════════════════╗
║          CONTRARIAN SIGNALS - Bad Traders Analysis          ║
╠══════════════════════════════════════════════════════════════╣
║ Total Bad Traders: 277  |  With Positions: 142  |  Signals: 8 ║
╚══════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────┐
│ BTC                                                🔴 STRONG │
│ Signal: SHORT    Confidence: 0.85    Traders: 45           │
│ Count:  L:82%(37) S:18%(8)                                 │
│ USD:    L:83%($890K) S:17%($180K)                          │
└─────────────────────────────────────────────────────────────┘
```

**What this means:**
- 🔴 **STRONG SHORT BTC:** 82% of bad traders are LONG on BTC
- **Contrarian action:** Consider shorting BTC (opposite of bad traders)
- **Confidence 0.85:** Very high confidence (out of 1.0)
- **45 traders:** Good sample size

## Common Questions

### Q: No signals appearing?

**A:** Bad traders might not have open positions right now. The system will keep monitoring every 90 seconds.

**Quick check:**
```bash
# See how many bad traders exist
sqlite3 analyzer/data/analyzed_traders.db "SELECT COUNT(*) FROM scored_traders WHERE score <= 5"

# If less than 10, lower the threshold in config.json:
# "min_traders_for_signal": 5
```

### Q: Want more/fewer signals?

**A:** Edit `contrarian/config.json`:

```json
{
  "bad_trader_score_threshold": 10,    // Include more traders (default: 5)
  "min_traders_for_signal": 5,         // Lower minimum (default: 10)
  "signal_thresholds": {
    "strong": 0.65,                    // Lower threshold (default: 0.70)
    "moderate": 0.55                   // Lower threshold (default: 0.60)
  }
}
```

### Q: Want to run just once (not continuous)?

**A:** Use the test script:

```bash
python3 contrarian/test_contrarian.py
```

This runs a single cycle and exits.

### Q: How to save signals for later analysis?

**A:** Signals are automatically saved to `contrarian/data/contrarian_signals.db`

Query them:
```bash
sqlite3 contrarian/data/contrarian_signals.db "SELECT * FROM contrarian_signals ORDER BY timestamp DESC LIMIT 10"
```

## What's Next?

1. **Monitor for 24 hours** - Let it collect signals
2. **Check historical accuracy** - Query the database to see signal patterns
3. **Integrate with trading** - Use signals in your trading strategy
4. **Customize thresholds** - Adjust config.json to match your risk tolerance

## Need Help?

- **Full documentation:** `contrarian/README.md`
- **Test the system:** `python3 contrarian/test_contrarian.py`
- **Check logs:** `cat contrarian.log`
- **Verify Phase 2 data:** `python3 analyzer/main.py`

---

**Pro Tip:** Run this in a `tmux` or `screen` session so it keeps running even when you disconnect:

```bash
# Create tmux session
tmux new -s contrarian

# Run the monitor
python3 contrarian/main.py

# Detach: Ctrl+B then D
# Reattach later: tmux attach -t contrarian
```
