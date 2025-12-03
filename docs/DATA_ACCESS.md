# Data Access Scripts

This document explains the utility scripts for accessing and exporting trader addresses from the database.

## query_addresses.py

Displays comprehensive statistics and top traders directly in your terminal.

### Usage

```bash
python3 query_addresses.py
```

### Output

The script provides four main sections:

1. **Database Statistics**
   - Total unique addresses tracked
   - Total trades recorded
   - Active addresses in the last hour
   - Active addresses in the last 24 hours
   - Total trading volume (USD)

2. **Top 10 Traders by Volume**
   - Ranked by total trading volume
   - Shows abbreviated address, volume, trade count, and activity dates

3. **Top 10 Traders by Trade Count**
   - Ranked by number of trades
   - Shows abbreviated address, trade count, volume, and activity dates

4. **10 Most Recent Addresses**
   - Shows the latest addresses seen trading
   - Useful for monitoring real-time activity

### When to Use

- Quick overview of database contents
- Identifying high-volume traders
- Monitoring recent activity
- Verifying the tracker is working correctly

---

## export_addresses.py

Exports all addresses from the database to a CSV file for further analysis.

### Usage

```bash
python3 export_addresses.py
```

### Output

- Creates `data/addresses_export.csv` with all addresses
- Prints export confirmation and database statistics

### CSV Format

The exported CSV contains the following columns:

| Column | Description |
|--------|-------------|
| `address` | Ethereum wallet address (0x...) |
| `first_seen` | Timestamp of first trade observed |
| `last_seen` | Timestamp of most recent trade |
| `trade_count` | Total number of trades made |
| `total_volume_usd` | Cumulative trading volume in USD |

### When to Use

- Importing data into Excel, Google Sheets, or other tools
- Performing custom analysis with pandas or R
- Creating backups of the address data
- Sharing data with team members
- Building custom reports or visualizations

### Example Workflow

```bash
# Export addresses
python3 export_addresses.py

# Use the CSV with pandas
import pandas as pd
df = pd.read_csv('data/addresses_export.csv')
print(df.describe())
```

---

## Requirements

Both scripts require:
- The tracker environment to be set up (dependencies installed)
- Access to the database file specified in `.env` (default: `data/addresses.db`)
- The tracker to have run and collected some data

## Notes

- Both scripts use the same configuration from `.env`
- They work even when the tracker is running
- No data is modified - these are read-only operations
- Scripts are safe to run multiple times
