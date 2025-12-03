# Hyperliquid Trader Analyzer - Phase 2

A sophisticated statistical analysis system that evaluates trader performance on Hyperliquid to identify those performing significantly worse than random chance.

## 🎯 Purpose

This analyzer performs rigorous statistical testing on trader performance to answer the question: **"Is this trader performing significantly worse than if they were trading randomly?"**

Unlike simple PnL tracking, this system uses multiple statistical methods including:
- One-sample t-tests against zero
- Monte Carlo simulations (1000+ iterations)
- Sharpe ratio calculations
- Expected value analysis

## 🏗️ Architecture

### Complete Isolation from Phase 1

This system is **completely independent** from the Phase 1 monitoring system:

- ✅ **Read-only access** to Phase 1 database (`fetcher/data/addresses.db`)
- ✅ **Separate database** for analysis results (`analyzer/data/analyzed_traders.db`)
- ✅ **Independent process** - runs as standalone service
- ✅ **Fault tolerant** - crashes won't affect Phase 1
- ✅ **Separate dashboard** - runs on port 5001 (Phase 1 uses 5000)

### Directory Structure

```
analyzer/
├── config/
│   └── config.yaml              # Configuration file
├── core/
│   ├── api_client.py           # Hyperliquid API wrapper
│   ├── statistics.py           # Statistical analysis engine
│   ├── database.py             # Database operations
│   └── config.py               # Configuration management
├── services/
│   ├── analyzer_service.py     # Main orchestration service
│   └── alert_service.py        # Alert system
├── dashboard/
│   └── app.py                  # Web dashboard (Flask)
├── data/
│   └── analyzed_traders.db     # Analysis results (created automatically)
├── logs/
│   ├── analyzer.log            # Main log file
│   └── bad_traders_alert.log   # Alert log (JSON lines)
├── main.py                      # Entry point
├── requirements.txt             # Dependencies
└── README.md                    # This file
```

## 📊 Statistical Methodology

### Scoring System (0-100)

The score represents statistical performance relative to random chance:

- **0-5**: Exceptionally bad (significantly worse than random, p < 0.01) ⚠️ **ALERT**
- **5-15**: Very poor (likely worse than random, p < 0.05)
- **15-40**: Below average but not statistically significant
- **40-60**: Random performance (no edge)
- **60-85**: Above average but not statistically significant
- **85-95**: Very good (likely better than random, p < 0.05)
- **95-100**: Exceptional (significantly better than random, p < 0.01)

### Statistical Tests

#### 1. One-Sample T-Test Against Zero
Tests if mean PnL per trade significantly differs from 0.

```python
H0: mean PnL = 0 (random performance)
H1: mean PnL ≠ 0 (significant edge or disadvantage)
```

#### 2. Monte Carlo Simulation (1000 iterations)
Simulates 1000 random traders making the same number of trades, randomly selecting from the actual PnL distribution.

**Example**: If a trader's total PnL is worse than 95% of simulated random traders, their score = 5 (bottom 5th percentile).

#### 3. Expected Value (EV) Analysis
```python
EV = (Avg Win × Win Rate) - (|Avg Loss| × Loss Rate)
```
Negative EV indicates long-term losing performance.

#### 4. Sharpe Ratio (Risk-Adjusted Returns)
```python
Sharpe = (Mean PnL / Std Dev) × √250
```
Measures return per unit of risk.

### Minimum Requirements

- **Minimum 30 trades**: Statistical significance threshold
- **P-value < 0.01**: 99% confidence for alerts
- **Score ≤ 5**: Bottom 5th percentile trigger

## 🚀 Installation

### Prerequisites

1. **Phase 1 must be running** and have collected some addresses in `fetcher/data/addresses.db`
2. Python 3.8+ installed
3. Virtual environment (recommended)

### Setup Steps

```bash
# Navigate to analyzer directory
cd analyzer

# Install dependencies
pip install -r requirements.txt

# Configuration is already set up in config/config.yaml
# You may edit it if needed
```

## ⚙️ Configuration

Edit `config/config.yaml` to customize behavior:

```yaml
api:
  base_url: "https://api.hyperliquid.xyz"
  rate_limit_calls: 20        # Max 20 requests per second
  rate_limit_period: 1
  timeout: 10
  max_retries: 3

analysis:
  min_trades: 30              # Minimum trades for analysis
  p_value_threshold: 0.01     # 99% confidence for alerts
  alert_score_threshold: 5    # Alert when score ≤ 5
  monte_carlo_iterations: 1000
  reanalysis_interval_days: 7 # Re-analyze weekly

database:
  phase1_db_path: "../fetcher/data/addresses.db"  # READ-ONLY
  phase2_db_path: "./data/analyzed_traders.db"
  batch_size: 100
  connection_timeout: 30

processing:
  concurrent_traders: 10      # Analyze 10 traders in parallel
  batch_processing_interval: 300  # 5 minutes between batches
  priority_recent_active_days: 7

dashboard:
  enabled: true
  host: "0.0.0.0"
  port: 5001                  # Different from Phase 1 (5000)
  auto_refresh_seconds: 10

alerts:
  console_enabled: true       # Print alerts to console
  log_file_enabled: true      # Write alerts to JSON log
  log_path: "./logs/bad_traders_alert.log"
  dashboard_enabled: true     # Show in dashboard

logging:
  level: "INFO"
  file: "./logs/analyzer.log"
  max_bytes: 10485760         # 10MB
  backup_count: 5
```

## 🎮 Usage

### Continuous Mode (Recommended)

Runs continuously, analyzing traders in batches every 5 minutes:

```bash
python main.py --mode continuous
```

This will:
1. Start the web dashboard at `http://localhost:5001`
2. Continuously analyze traders from Phase 1 database
3. Trigger alerts for exceptionally bad traders
4. Run until stopped with Ctrl+C

### One-Time Mode

Analyze a batch of traders and exit:

```bash
# Analyze 50 traders
python main.py --mode once --limit 50

# Analyze all pending traders
python main.py --mode once
```

### Custom Configuration

```bash
python main.py --config /path/to/config.yaml
```

## 📈 Web Dashboard

Access the dashboard at `http://localhost:5001`

### Features:

1. **Real-time Statistics**
   - Total traders analyzed
   - Number of bad traders detected
   - Analyzed in last 24 hours
   - Average score

2. **Recent Alerts**
   - Last 10 exceptionally bad traders detected
   - Score, PnL, and trade count
   - Timestamp of detection

3. **Score Distribution**
   - Histogram showing trader performance categories
   - Exceptionally Bad to Exceptional

4. **Worst Performers**
   - Top 10 worst traders by score
   - Detailed metrics for each

### Auto-Refresh

Dashboard automatically refreshes every 10 seconds (configurable).

## 🚨 Alert System

When a trader with score ≤ 5 is detected, alerts are triggered on multiple channels:

### 1. Console Alert

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

### 2. Log File Alert (`logs/bad_traders_alert.log`)

JSON format for easy parsing:

```json
{
    "timestamp": "2025-01-21T15:30:45Z",
    "address": "0x742d...9f31",
    "score": 3,
    "total_pnl": -12450.32,
    "p_value": 0.0008,
    "num_trades": 501,
    "alert_reason": "score_below_5_threshold"
}
```

### 3. Dashboard Alert

Appears in real-time on the dashboard's "Recent Alerts" section.

## 📊 Database Schema

### Phase 2 Database: `analyzer/data/analyzed_traders.db`

#### Table: `scored_traders`

| Column | Type | Description |
|--------|------|-------------|
| `address` | TEXT | Trader's Ethereum address (PK) |
| `score` | INTEGER | Performance score (0-100) |
| `total_pnl` | REAL | Total PnL across all trades |
| `mean_pnl_per_trade` | REAL | Average PnL per trade |
| `std_dev` | REAL | Standard deviation of PnL |
| `sharpe_ratio` | REAL | Risk-adjusted returns |
| `expected_value` | REAL | Expected value per trade |
| `t_statistic` | REAL | T-test statistic |
| `p_value` | REAL | Statistical significance |
| `monte_carlo_percentile` | REAL | Percentile from simulation |
| `num_trades` | INTEGER | Number of trades analyzed |
| `win_rate` | REAL | Win rate (0-1) |
| `avg_win` | REAL | Average winning trade |
| `avg_loss` | REAL | Average losing trade |
| `last_analyzed` | TIMESTAMP | When last analyzed |
| `is_statistically_bad` | BOOLEAN | True if score < 5 and p < 0.01 |

#### Table: `analysis_log`

Tracks all analysis attempts for debugging.

## 🔧 Performance

### Expected Throughput

With default settings (10 concurrent traders, 20 API req/sec):
- **~100-200 traders per hour**
- Depends on API response time and rate limits

### Optimization Tips

1. **Increase concurrency**: Set `concurrent_traders: 20` for faster processing
2. **Adjust batch interval**: Reduce `batch_processing_interval` for more frequent runs
3. **Cache utilization**: Cache is 5 minutes by default, preventing redundant API calls

### Resource Usage

- **Memory**: ~100-150 MB
- **CPU**: 5-10% during active analysis
- **Network**: 10-50 KB/s (API calls)
- **Disk**: ~1 MB per 10,000 analyzed traders

## 🐛 Troubleshooting

### "Phase 1 database not found"

**Solution**: Ensure Phase 1 is running and has created `fetcher/data/addresses.db`:
```bash
# Check if Phase 1 database exists
ls -la ../fetcher/data/addresses.db

# If not, start Phase 1 first
cd ..
python fetcher/main.py
```

### "API rate limit exceeded"

**Solution**: Reduce `rate_limit_calls` or `concurrent_traders` in config.yaml:
```yaml
api:
  rate_limit_calls: 10  # Reduce from 20
processing:
  concurrent_traders: 5  # Reduce from 10
```

### "No addresses to analyze"

**Causes**:
1. Phase 1 hasn't collected any addresses yet (wait for it to run)
2. All addresses already analyzed recently (normal, will wait for re-analysis interval)

**Solution**: Wait for Phase 1 to collect more addresses or reduce `reanalysis_interval_days`.

### Dashboard not loading

**Solution**:
```bash
# Check if port 5001 is available
lsof -i :5001

# Try a different port in config.yaml
dashboard:
  port: 5002
```

## 📋 Examples

### Example 1: First-Time Setup

```bash
# 1. Make sure Phase 1 is running
cd /path/to/hyper-tracker
python fetcher/main.py &

# 2. Wait for Phase 1 to collect some addresses (5-10 minutes)

# 3. Start analyzer
cd analyzer
python main.py --mode once --limit 10

# 4. Check results
open http://localhost:5001
```

### Example 2: Production Deployment

```bash
# Run in background with nohup
nohup python main.py --mode continuous > /dev/null 2>&1 &

# Or use systemd (see below)
```

### Example 3: Query Results

```python
import sqlite3

# Connect to database
conn = sqlite3.connect('analyzer/data/analyzed_traders.db')

# Get all bad traders
bad_traders = conn.execute("""
    SELECT address, score, total_pnl, num_trades
    FROM scored_traders
    WHERE is_statistically_bad = 1
    ORDER BY score ASC
""").fetchall()

for addr, score, pnl, trades in bad_traders:
    print(f"{addr}: score={score}, pnl=${pnl:.2f}, trades={trades}")
```

## 🚀 Deployment

### Systemd Service (Linux)

Create `/etc/systemd/system/hyperliquid-analyzer.service`:

```ini
[Unit]
Description=Hyperliquid Trader Analyzer
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/hyper-tracker/analyzer
ExecStart=/path/to/venv/bin/python main.py --mode continuous
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable hyperliquid-analyzer
sudo systemctl start hyperliquid-analyzer
sudo systemctl status hyperliquid-analyzer
```

### Docker (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY analyzer/requirements.txt .
RUN pip install -r requirements.txt

COPY analyzer/ .

CMD ["python", "main.py", "--mode", "continuous"]
```

## 📚 Understanding the Statistics

### Why These Tests?

1. **T-Test**: Determines if performance is statistically different from random
2. **Monte Carlo**: Provides intuitive percentile ranking against randomness
3. **Sharpe Ratio**: Accounts for risk - a trader might be profitable but too risky
4. **Expected Value**: Shows long-term expectation per trade

### Example Analysis

**Trader A: Score = 3**
- Total PnL: -$10,000
- 500 trades
- Win rate: 48%
- P-value: 0.003 (highly significant)
- Monte Carlo: 3rd percentile (97% of random traders did better)

**Interpretation**: This trader is losing significantly more than if they traded randomly. Only 3% of simulated random traders performed worse. With 99.7% confidence, this is not due to chance.

## 🔐 Security Notes

- All data is read-only from Phase 1
- No modification of Phase 1 database
- Dashboard has no authentication (localhost only by default)
- For production, add nginx reverse proxy with auth

## 📞 Support

- Check logs: `analyzer/logs/analyzer.log`
- Check alerts: `analyzer/logs/bad_traders_alert.log`
- Database issues: Verify Phase 1 is running
- API issues: Check Hyperliquid API status

## 🎯 Future Enhancements

Potential additions:
- Email/Telegram notifications
- Machine learning models for prediction
- Historical backtesting
- Multi-exchange support
- API for external integrations

---

**Built for Hyperliquid traders | Phase 2 Statistical Analysis System**
