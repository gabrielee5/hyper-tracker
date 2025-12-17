# Trading Strategy Guide

This simulator supports two different trading strategies. Choose which one to run based on your requirements.

## Strategy 1: Default Multi-Asset Strategy

**Files:**
- `main.py` - Launcher
- `simulator.py` - Main simulator
- `position_sizer.py` - Position sizing logic
- `config.json` - Configuration

**Characteristics:**
- Trades up to 10 different assets
- Confidence-weighted allocation across all qualifying signals
- 40% max position per asset
- Min confidence threshold: 50%
- Dynamically allocates based on available signals

**How to run:**
```bash
python main.py
```

**Dashboard:** http://localhost:5003

---

## Strategy 2: Three-Asset Strategy (BTC, SOL, ETH)

**Files:**
- `main_three_asset.py` - Launcher
- `simulator_three_asset.py` - Main simulator
- `position_sizer_three_asset.py` - Position sizing logic
- `config_three_asset.json` - Configuration

**Characteristics:**
- **Only trades BTC, SOL, and ETH** (all other assets ignored)
- Each asset has max allocation of **1/3 of total capital** ($33,333 per asset)
- Actual allocation = **confidence × max allocation**
- **No confidence threshold** (accepts any confidence level including 5%)
- Tracks and reports cash not invested

**Allocation Formula:**
```
Per-asset max = Total Capital / 3
Allocation = Confidence × Per-asset max

Example with $100k capital:
- BTC @ 70% confidence → $23,333 (0.70 × $33,333)
- SOL @ 40% confidence → $13,333 (0.40 × $33,333)
- ETH @ 85% confidence → $28,333 (0.85 × $33,333)

Total invested: $65,000
Cash reserve: $35,000 (35%)
```

**How to run:**
```bash
python main_three_asset.py
```

**Dashboard:** http://localhost:5004

---

## Key Differences

| Feature | Default Strategy | Three-Asset Strategy |
|---------|-----------------|---------------------|
| Assets | Up to 10 different | Only BTC, SOL, ETH |
| Max per position | 40% | 33.3% (1/3) |
| Min confidence | 50% | 0% (no threshold) |
| Allocation logic | Confidence-weighted normalized | Direct: confidence × 1/3 |
| Database | `simulator.db` | `simulator_three_asset.db` |
| Dashboard port | 5003 | 5004 |
| Log file | `simulator.log` | `simulator_three_asset.log` |

---

## Cash Tracking

The **Three-Asset Strategy** explicitly tracks and logs cash reserves:

- Logs show "Cash reserve: $X (Y%)" after each rebalance
- Dashboard status includes `cash_reserve` and `cash_reserve_pct`
- Cash reserve = Portfolio value - Sum of all position values

You'll always have cash on hand since allocation = confidence × max, not just max.

---

## Running Both Simultaneously

You can run both strategies at the same time since they use:
- Separate databases
- Separate log files
- Different dashboard ports (5003 vs 5004)

Just open two terminal windows and run each strategy's launcher.
