# Hyperliquid Trader Address Tracker

A real-time monitoring system for tracking trader addresses on the Hyperliquid decentralized exchange. This system connects to Hyperliquid's WebSocket API, extracts trader addresses from live trades, stores them in a persistent database, and provides a beautiful web dashboard for monitoring.

## Features

- **Real-time Trade Monitoring**: WebSocket connection to Hyperliquid for live trade data
- **Configurable Coin Selection**: Track specific coins or all available trading pairs
- **Address Extraction**: Automatically extracts both buyer and seller addresses from trades
- **Persistent Storage**: SQLite database with deduplication and volume tracking
- **Batch Processing**: Efficient batch insertion with configurable batch sizes
- **Web Dashboard**: Beautiful, real-time dashboard for monitoring statistics
- **Volume Tracking**: Tracks total trading volume per address (prepared for Phase 2 analytics)
- **Comprehensive Logging**: Detailed logs for debugging and monitoring
- **Graceful Shutdown**: Properly handles interrupts and flushes pending data

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Main Application                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │  WebSocket Manager (Hyperliquid SDK)             │  │
│  │  - Subscribe to trades for selected coins        │  │
│  │  - Handle reconnections automatically            │  │
│  └──────────────────────────────────────────────────┘  │
│                        │                                 │
│                        ▼                                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Address Tracker                                  │  │
│  │  - Extract buyer & seller addresses              │  │
│  │  - Batch processing with in-memory queue         │  │
│  └──────────────────────────────────────────────────┘  │
│                        │                                 │
│                        ▼                                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Storage Layer (SQLite)                           │  │
│  │  - Unique addresses with trade counts            │  │
│  │  - Volume tracking per address                   │  │
│  │  - Historical trade data                         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Web Dashboard (Flask)                            │  │
│  │  - Real-time statistics                          │  │
│  │  - Recent addresses                              │  │
│  │  - Top traders                                   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Setup Steps

1. **Clone or navigate to the project directory**:
   ```bash
   cd hyper-tracker
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the application**:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` to customize your configuration:
   ```env
   NETWORK=mainnet
   TRACK_ALL_COINS=false
   SELECTED_COINS=BTC,ETH,SOL,ARB
   DASHBOARD_ENABLED=true
   DASHBOARD_PORT=5000
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NETWORK` | Network to use (mainnet/testnet) | `mainnet` |
| `TRACK_ALL_COINS` | Track all available coins | `false` |
| `SELECTED_COINS` | Comma-separated list of coins to track | `BTC,ETH,SOL,ARB` |
| `DATABASE_PATH` | Path to SQLite database | `data/addresses.db` |
| `BATCH_SIZE` | Addresses to accumulate before flushing | `1000` |
| `DEDUP_INTERVAL` | Seconds between deduplication runs | `60` |
| `DASHBOARD_ENABLED` | Enable web dashboard | `true` |
| `DASHBOARD_PORT` | Dashboard port | `5000` |
| `DASHBOARD_HOST` | Dashboard host | `0.0.0.0` |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
| `LOG_FILE` | Path to log file | `logs/tracker.log` |

### Coin Selection Options

**Option 1: Track Specific Coins**
```env
TRACK_ALL_COINS=false
SELECTED_COINS=BTC,ETH,SOL,AVAX,MATIC
```

**Option 2: Track All Available Coins**
```env
TRACK_ALL_COINS=true
```

## Usage

### Running the Tracker

Start the tracker from the `src` directory:

```bash
cd src
python main.py
```

You should see output like:
```
================================================================================
HYPERLIQUID TRADER ADDRESS TRACKER
================================================================================
2025-01-21 10:30:15 - INFO - Logging initialized - Level: INFO, File: logs/tracker.log
2025-01-21 10:30:15 - INFO - Starting Hyperliquid Tracker
2025-01-21 10:30:15 - INFO - Network: mainnet
2025-01-21 10:30:16 - INFO - Successfully connected to Hyperliquid
2025-01-21 10:30:16 - INFO - Tracking 4 coins: BTC, ETH, SOL, ARB
2025-01-21 10:30:16 - INFO - Dashboard started at http://0.0.0.0:5000
2025-01-21 10:30:16 - INFO - Tracker started successfully - press Ctrl+C to stop
```

### Accessing the Dashboard

Open your browser and navigate to:
```
http://localhost:5000
```

The dashboard displays:
- **Total unique addresses** tracked
- **Total trades** processed
- **Total trading volume** in USD
- **Active addresses** (1h and 24h windows)
- **Trades by coin** breakdown
- **Recent addresses** with trade counts and volumes

The dashboard auto-refreshes every 5 seconds.

### Graceful Shutdown

Press `Ctrl+C` to stop the tracker. It will:
1. Stop accepting new trades
2. Flush all pending addresses to the database
3. Display final statistics
4. Close all connections properly

## Database Schema

### Addresses Table
```sql
CREATE TABLE addresses (
    address TEXT PRIMARY KEY,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trade_count INTEGER DEFAULT 1,
    total_volume_usd REAL DEFAULT 0.0
);
```

### Trades Table (Phase 2 Ready)
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL,
    coin TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    size REAL NOT NULL,
    value_usd REAL NOT NULL,
    trade_hash TEXT NOT NULL,
    trade_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (address) REFERENCES addresses(address)
);
```

## API Endpoints

The dashboard exposes REST API endpoints:

### Get Statistics
```
GET /api/stats
```
Returns overall statistics including address counts, volumes, and activity.

### Get Recent Addresses
```
GET /api/addresses?limit=100
```
Returns the most recently seen addresses.

### Get Top Traders
```
GET /api/top-traders?limit=100&by=volume
```
Parameters:
- `by`: Sort by `volume` or `trades`
- `limit`: Number of results (default: 100)

## Project Structure

```
hyper-tracker/
├── fetcher/
│   ├── __init__.py
│   ├── main.py              # Entry point and main application
│   ├── config.py            # Configuration management
│   ├── connection.py        # Hyperliquid WebSocket connection
│   ├── address_tracker.py   # Address extraction and batch processing
│   ├── storage.py           # Database operations
│   ├── dashboard.py         # Web dashboard
│   └── utils.py             # Utility functions and logging
├── data/
│   └── addresses.db         # SQLite database (auto-created)
├── logs/
│   └── tracker.log          # Application logs
├── requirements.txt         # Python dependencies
├── .env.example             # Example configuration
└── README.md                # This file
```

## Design Decisions

### Why SQLite?
- Handles millions of rows efficiently
- Zero configuration required
- Perfect for single-instance applications
- Easy to export/migrate to PostgreSQL later
- ACID compliance for data integrity

### Why Batch Processing?
- Reduces database lock contention
- Better performance under high trade volume
- The 60-second deduplication window is acceptable
- Efficient memory usage

### Why Subscribe Per Coin?
- Hyperliquid doesn't provide a global trade feed
- Per-coin subscriptions ensure complete coverage
- The SDK handles multiple subscriptions efficiently
- Allows selective tracking for resource optimization

### Phase 2 Preparation
The system is designed to be easily extended with trader analysis features:
- Volume tracking is already implemented
- Trade history table is ready for detailed analytics
- Modular design allows easy addition of new features
- API endpoints can be extended for custom queries

## Logging

Logs are written to both console and file:
- **Console**: Shows INFO level and above with timestamps
- **File**: Captures all DEBUG level logs for troubleshooting

Log file location: `logs/tracker.log`

Example log entries:
```
2025-01-21 10:30:16 - INFO - Subscribed to BTC
2025-01-21 10:30:16 - INFO - Subscribed to ETH
2025-01-21 10:31:16 - INFO - Flushed batch: 150 new addresses added
2025-01-21 10:32:16 - INFO - Statistics - Trades: 543, Total Addresses: 1250, Active (1h): 234
```

## Troubleshooting

### Connection Issues
- Verify your internet connection
- Check if Hyperliquid API is accessible
- Try switching between mainnet and testnet

### No Trades Appearing
- Verify selected coins are valid
- Check if markets are active
- Review logs for subscription errors

### Database Errors
- Ensure `data/` directory has write permissions
- Check disk space availability
- Verify database file isn't corrupted

### Dashboard Not Loading
- Check if port 5000 is available
- Verify `DASHBOARD_ENABLED=true` in `.env`
- Review Flask logs for errors

## Performance Considerations

- **Memory Usage**: Batch processing keeps memory footprint low (~50MB typical)
- **CPU Usage**: Minimal (<5% on modern hardware)
- **Network**: ~1-2 KB/s per coin tracked
- **Database Size**: ~1MB per 10,000 unique addresses

## Future Enhancements (Phase 2)

The codebase is prepared for:
- Trader behavior analysis
- Profit/loss tracking
- Trading pattern detection
- Portfolio analysis
- Alert system for whale movements
- Historical data analysis
- Machine learning integration

## License

This project is provided as-is for educational and monitoring purposes.

## Support

For issues or questions:
1. Check the logs in `logs/tracker.log`
2. Review the Hyperliquid API documentation
3. Verify your configuration in `.env`

---

**Built with the official Hyperliquid Python SDK**
