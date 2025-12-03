# Hyperliquid Trader Analyzer - Quick Start Guide

## 🚀 5-Minute Setup

### Prerequisites Check

1. **Phase 1 must be running** to collect trader addresses:
```bash
# Check if Phase 1 database exists
ls -la fetcher/data/addresses.db
# If not found, start Phase 1 first:
python fetcher/main.py
```

2. **Python 3.8+** installed
3. **Dependencies** installed (will be installed automatically)

### Step 1: Install Dependencies

```bash
cd analyzer
pip install -r requirements.txt
```

### Step 2: Run the Analyzer

**Option A: One-time analysis (recommended for first run)**
```bash
python3 main.py --mode once --limit 10
```

This will:
- Analyze 10 traders from Phase 1 database
- Show results in console
- Exit when complete

**Option B: Continuous mode**
```bash
python3 main.py --mode continuous
```

This will:
- Start web dashboard at http://localhost:5001
- Continuously analyze traders every 5 minutes
- Run until stopped with Ctrl+C

### Step 3: View Results

**Web Dashboard**: Open http://localhost:5001 in your browser

**Database Query**:
```bash
sqlite3 data/analyzed_traders.db "SELECT address, score, total_pnl, num_trades FROM scored_traders ORDER BY score ASC LIMIT 10;"
```

**Alert Log**:
```bash
cat logs/bad_traders_alert.log
```

---

## 📊 Understanding the Output

### Console Output Example

When analyzer finds a bad trader:

```
🚨 ALERT: Exceptionally Bad Trader Detected!
═══════════════════════════════════════════════
Address:       0x742d...9f31
Score:         3/100 (Bottom 3rd percentile)
Total PnL:     -$12,450.32
P-Value:       0.0008 (highly significant)
Trades:        501
Win Rate:      42.3%
Expected Val:  -$10.50 per trade
═══════════════════════════════════════════════
```

### What the Metrics Mean

- **Score 0-100**: Percentile rank against random traders
  - 0 = Worst (bottom 0th percentile)
  - 50 = Random performance
  - 100 = Best (top 100th percentile)

- **P-Value**: Statistical significance
  - < 0.01 = 99% confidence (highly significant)
  - < 0.05 = 95% confidence (significant)
  - \> 0.05 = Not statistically significant

- **Expected Value**: Average profit/loss per trade
  - Negative = Losing money per trade on average

- **Sharpe Ratio**: Risk-adjusted returns
  - Negative = Losing money
  - 0-1 = Poor
  - 1-2 = Good
  - \> 2 = Excellent

---

## ⚙️ Configuration (Optional)

Edit `config/config.yaml` to customize:

```yaml
# Analyze faster (more concurrency)
processing:
  concurrent_traders: 20      # Default: 10

# Lower alert threshold (catch more bad traders)
analysis:
  alert_score_threshold: 10   # Default: 5

# Re-analyze more frequently
analysis:
  reanalysis_interval_days: 3 # Default: 7
```

---

## 🐛 Troubleshooting

### "Phase 1 database not found"

**Cause**: Phase 1 hasn't created the database yet

**Solution**:
```bash
# Start Phase 1 and wait 5-10 minutes
cd ..
python fetcher/main.py
```

### "No addresses to analyze"

**Cause**: All addresses already analyzed or Phase 1 has no data yet

**Solution**:
- Wait for Phase 1 to collect more addresses
- Or reduce `reanalysis_interval_days` in config

### "API rate limit exceeded"

**Cause**: Too many concurrent requests

**Solution**: Reduce concurrency in `config/config.yaml`:
```yaml
processing:
  concurrent_traders: 5  # Reduce from 10
```

### Dashboard not loading

**Solution**: Check if port 5001 is available:
```bash
lsof -i :5001
# If in use, change port in config.yaml
```

---

## 📁 Output Files

- `data/analyzed_traders.db` - SQLite database with all analysis results
- `logs/analyzer.log` - Main application log
- `logs/bad_traders_alert.log` - JSON log of alerts (one per line)

---

## 🎯 Next Steps

1. **View Dashboard**: http://localhost:5001
2. **Query Database**: See `README.md` for SQL query examples
3. **Customize Alerts**: Edit `config/config.yaml`
4. **Production Deployment**: See `README.md` for systemd service setup

---

## 📞 Quick Reference

```bash
# Run once, analyze 50 traders
python3 main.py --mode once --limit 50

# Run continuously with dashboard
python3 main.py --mode continuous

# Stop analyzer
Ctrl+C

# View logs
tail -f logs/analyzer.log

# View alerts
cat logs/bad_traders_alert.log | jq  # If jq installed

# Query worst traders
sqlite3 data/analyzed_traders.db \
  "SELECT address, score, total_pnl FROM scored_traders \
   WHERE is_statistically_bad = 1 ORDER BY score ASC;"
```

---

**Ready to start? Run:** `python3 main.py --mode once --limit 10`
