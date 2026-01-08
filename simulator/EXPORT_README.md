# Simulator Data Export Tool

This tool exports data from the simulator database to CSV files for analysis.

## Quick Start

```bash
# Export all data from the three-asset simulator (default)
python3 export_to_csv.py

# Export all data from a specific database
python3 export_to_csv.py --db ../data/simulator_run2.db

# Export only specific table
python3 export_to_csv.py --table trades

# Export summary reports only
python3 export_to_csv.py --summary

# Export without timestamp in filename
python3 export_to_csv.py --no-timestamp
```

## What Gets Exported

### Raw Tables
- **portfolio_state.csv** - Portfolio snapshots over time
- **positions.csv** - Current open positions
- **trades.csv** - All trade executions
- **rebalance_history.csv** - Rebalancing events
- **performance_history.csv** - Performance metrics over time

### Summary Reports
- **portfolio_summary.csv** - Comprehensive equity curve with cash breakdown
- **trade_analysis.csv** - Enhanced trade data with P&L calculations and outcomes
- **performance_metrics.csv** - Performance metrics formatted for analysis

## Output Location

All CSV files are saved to:
```
/Users/gabrielefabietti/projects/hyper-tracker/exports/simulator/
```

## Example Output

After running the export, you'll see something like:

```
✓ Connected to database: ../data/simulator_three_asset.db

================================================================================
DATABASE SUMMARY
================================================================================
Portfolio snapshots: 1129
Open positions: 3
Total trades: 2527
Total fees paid: $802.35
Latest equity: $99673.37 (-0.33%)
Rebalancing events: 1090
================================================================================

✓ Exported portfolio_state: 1129 rows → .../portfolio_state_20260108_162503.csv
✓ Exported trades: 2527 rows → .../trades_20260108_162503.csv
...
```

## Analyzing Exported Data

The CSV files can be analyzed using:

- **Excel/Google Sheets** - For quick viewing
- **Python/Pandas** - For detailed analysis
- **Jupyter Notebooks** - For interactive exploration
- **BI Tools** - Like Tableau, Power BI, etc.

### Example: Load in Python

```python
import pandas as pd

# Load trade data
trades = pd.read_csv('exports/trade_analysis_20260108_162503.csv')

# Analyze performance
print(f"Total trades: {len(trades)}")
print(f"Win rate: {(trades['pnl'] > 0).sum() / len(trades) * 100:.2f}%")
print(f"Total P&L: ${trades['pnl'].sum():.2f}")

# Load equity curve
portfolio = pd.read_csv('exports/portfolio_summary_20260108_162503.csv')
portfolio['timestamp'] = pd.to_datetime(portfolio['timestamp'])

# Plot equity curve
import matplotlib.pyplot as plt
plt.plot(portfolio['timestamp'], portfolio['total_equity'])
plt.title('Equity Curve')
plt.show()
```

## Available Databases

Check which simulator databases are available:

```bash
ls -lh /Users/gabrielefabietti/projects/hyper-tracker/data/simulator*.db
```

Current databases:
- `simulator_three_asset.db` - Three-asset strategy (BTC, SOL, ETH)
- `simulator_run1.db`, `simulator_run2.db`, etc. - Previous simulation runs

## Notes

- **Timestamps**: By default, files include timestamp suffix to avoid overwriting
- **No Timestamp**: Use `--no-timestamp` to create files without timestamp (useful for automated pipelines)
- **Database Path**: Default is `../data/simulator_three_asset.db` relative to the script location
