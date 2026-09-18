# Data Access Scripts

The utility scripts for reading and exporting the address pool that
`pipeline/fetcher` collects.

Both live in `pipeline/fetcher/` and resolve their own paths, so they run from
anywhere:

```bash
python pipeline/fetcher/query_addresses.py
python pipeline/fetcher/export_addresses.py
```

Every other module has its own exporter — see
[CONFIGURATION.md](CONFIGURATION.md) for where each database lives, and the
module READMEs for their export flags.

## query_addresses.py

Displays comprehensive statistics and top traders directly in your terminal.

### Usage

```bash
python pipeline/fetcher/query_addresses.py
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
python pipeline/fetcher/export_addresses.py
```

### Output

- Creates `exports/addresses_export_<timestamp>.csv` with all addresses
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
python pipeline/fetcher/export_addresses.py
# -> exports/addresses_export_<timestamp>.csv
```

```python
import pandas as pd
df = pd.read_csv("exports/addresses_export_20260918_120000.csv")
print(df.describe())
```

---

## Requirements

Both scripts require:
- The tracker environment to be set up (dependencies installed)
- `data/addresses.db`, created by `pipeline/fetcher` (path set by `DATABASE_PATH` in `.env`)
- The tracker to have run and collected some data

## Notes

- Both scripts use the same configuration from `.env`
- They work even when the tracker is running
- No data is modified - these are read-only operations
- Scripts are safe to run multiple times
