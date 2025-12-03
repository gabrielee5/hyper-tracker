# CSV Export Tool for Contrarian Signals

## Overview

This tool exports data from the contrarian signals database (`contrarian_signals.db`) to CSV format for analysis in Excel, Google Sheets, or other tools.

## Location

The export script is located at:
```
contrarian/export_signals_csv.py
```

## Quick Start

### Export All Signals
```bash
python3 contrarian/export_signals_csv.py
```

This creates a file in the `data/` folder like: `data/contrarian_signals_20251203_155257.csv`

### Show Database Statistics
```bash
python3 contrarian/export_signals_csv.py --stats
```

Shows:
- Total number of signals
- Date range
- Signal breakdown (LONG/SHORT/NEUTRAL by strength)
- Top 10 coins by signal count
- Position snapshot statistics

## Usage Examples

### Export Specific Coin
```bash
# Export only BTC signals
python3 contrarian/export_signals_csv.py --coin BTC

# Export only ETH signals
python3 contrarian/export_signals_csv.py --coin ETH
```

### Limit Number of Records
```bash
# Export last 100 signals
python3 contrarian/export_signals_csv.py --limit 100

# Export last 50 BTC signals
python3 contrarian/export_signals_csv.py --coin BTC --limit 50
```

### Custom Output File
```bash
# Save to specific file (saved in data/ folder)
python3 contrarian/export_signals_csv.py --output my_signals.csv

# Use short flag (also saved in data/ folder)
python3 contrarian/export_signals_csv.py -o btc_analysis.csv --coin BTC

# Use absolute path to save elsewhere
python3 contrarian/export_signals_csv.py -o /path/to/exports/signals.csv
```

### Export Position Snapshots
```bash
# Export position data instead of signals
python3 contrarian/export_signals_csv.py --type positions

# Export BTC positions only
python3 contrarian/export_signals_csv.py --type positions --coin BTC
```

## Command-Line Options

| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--help` | `-h` | Show help message | `-h` |
| `--db` | | Database path | `--db data/contrarian_signals.db` |
| `--output` | `-o` | Output CSV file | `-o signals.csv` |
| `--type` | `-t` | Data type (signals/positions) | `-t positions` |
| `--limit` | `-l` | Max records to export | `-l 100` |
| `--coin` | `-c` | Filter by coin | `-c BTC` |
| `--stats` | `-s` | Show statistics only | `-s` |

## CSV Format

### Signals CSV Columns

The exported signals CSV contains the following columns:

| Column | Description |
|--------|-------------|
| `id` | Unique signal ID |
| `timestamp` | When signal was generated |
| `coin` | Cryptocurrency symbol |
| `signal_direction` | LONG, SHORT, or NEUTRAL |
| `signal_strength` | STRONG, MODERATE, WEAK, or NONE |
| `bad_traders_total` | Number of bad traders with positions |
| `long_count` | Number of traders with long positions |
| `short_count` | Number of traders with short positions |
| `long_percentage` | Percentage of traders long (0-100) |
| `short_percentage` | Percentage of traders short (0-100) |
| `long_usd_value` | Total USD value of long positions |
| `short_usd_value` | Total USD value of short positions |
| `long_usd_percentage` | Percentage of USD value in longs |
| `short_usd_percentage` | Percentage of USD value in shorts |
| `confidence_score` | Signal confidence (0.0-1.0) |
| `primary_metric` | Main metric used (count or size) |

### Position Snapshots CSV Columns

| Column | Description |
|--------|-------------|
| `id` | Unique snapshot ID |
| `timestamp` | When snapshot was taken |
| `address` | Trader wallet address |
| `coin` | Cryptocurrency symbol |
| `side` | LONG or SHORT |
| `size` | Position size |
| `position_value_usd` | USD value of position |
| `entry_price` | Entry price |
| `leverage_value` | Leverage used |
| `unrealized_pnl` | Unrealized profit/loss |

## Sample Output

### Statistics Output
```
============================================================
DATABASE STATISTICS
============================================================

Total Signals: 1845
Date Range: 2025-12-02 17:37:03 to 2025-12-03 14:47:55

Signal Breakdown:
  NEUTRAL  NONE      :  652 signals
  LONG     STRONG    :  541 signals
  LONG     MODERATE  :  347 signals
  SHORT    STRONG    :  161 signals
  SHORT    MODERATE  :  144 signals

Top 10 Coins by Signal Count:
  BTC     :   72 signals
  ETH     :   72 signals
  SOL     :   72 signals
  ...

Total Position Snapshots: 81314
Date Range: 2025-12-02 17:37:03 to 2025-12-03 14:47:55
============================================================
```

### CSV Export Output
```
Exporting from: /path/to/data/contrarian_signals.db
✓ Exported 100 signals to: /path/to/data/contrarian_signals_20251203_155257.csv
File size: 18.45 KB

You can now open this file in Excel, Google Sheets, or any CSV viewer.
```

**Note:** All CSV files are automatically saved to the `data/` folder (same location as the database) unless you specify an absolute path.

## Analysis Tips

### In Excel/Google Sheets

1. **Sort by confidence**: Find highest confidence signals
2. **Filter by coin**: Analyze specific cryptocurrencies
3. **Group by signal_direction**: Compare LONG vs SHORT trends
4. **Create pivot tables**: Analyze signal patterns over time
5. **Calculate win rates**: Compare signals against actual price movements

### Useful Formulas

**Average confidence for LONG signals:**
```excel
=AVERAGEIF(D:D,"LONG",O:O)
```

**Count STRONG signals for BTC:**
```excel
=COUNTIFS(C:C,"BTC",E:E,"STRONG")
```

**Total USD value across all positions:**
```excel
=SUM(K:K)+SUM(L:L)
```

## Integration with Analysis Tools

### Python/Pandas
```python
import pandas as pd

# Load CSV
df = pd.read_csv('contrarian_signals_20251203.csv')

# Convert timestamp
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Filter strong signals
strong_signals = df[df['signal_strength'] == 'STRONG']

# Analyze by coin
btc_signals = df[df['coin'] == 'BTC']
```

### R
```r
# Load CSV
signals <- read.csv('contrarian_signals_20251203.csv')

# Convert timestamp
signals$timestamp <- as.POSIXct(signals$timestamp)

# Summary statistics
summary(signals$confidence_score)
```

## Troubleshooting

### "Database not found" Error
```bash
# Make sure you're in the right directory
cd /Users/gabrielefabietti/projects/hyper-tracker

# Or specify full path
python3 contrarian/export_signals_csv.py --db data/contrarian_signals.db
```

### "No signals found"
The database might be empty. Run the contrarian system first:
```bash
./run_contrarian.sh
```

### Large CSV Files
If exporting all data creates very large files, use `--limit`:
```bash
# Export most recent 1000 signals
python3 contrarian/export_signals_csv.py --limit 1000
```

## Automation

### Daily Export Script
```bash
#!/bin/bash
# Save as: export_daily.sh

DATE=$(date +%Y%m%d)
python3 contrarian/export_signals_csv.py \
  --output "exports/signals_${DATE}.csv" \
  --limit 1000

echo "Daily export complete: signals_${DATE}.csv"
```

### Cron Job (Linux/Mac)
```bash
# Export signals daily at 6 PM
0 18 * * * cd /path/to/hyper-tracker && python3 contrarian/export_signals_csv.py -o exports/daily_$(date +\%Y\%m\%d).csv
```

## File Organization

Directory structure after exports:
```
hyper-tracker/
├── contrarian/
│   └── export_signals_csv.py
└── data/
    ├── contrarian_signals.db
    ├── contrarian_signals_20251201_143022.csv  # Auto-generated exports
    ├── contrarian_signals_20251202_094533.csv
    └── btc_analysis.csv                         # Custom named exports
```

**Note:** All CSV exports are saved in the `data/` folder by default. Use an absolute path with `-o` if you want to save elsewhere.

## Additional Resources

- See database schema in: `contrarian/core/database.py`
- Web dashboard: `http://127.0.0.1:5000` (when running)
- Terminal dashboard: Output from `./run_contrarian.sh`

## Support

For issues:
1. Check that contrarian system has been run (database exists)
2. Verify database path is correct
3. Try `--stats` flag to check database contents
4. Check logs: `logs/contrarian.log`
