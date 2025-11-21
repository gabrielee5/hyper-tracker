# System Architecture & Design Decisions

## Overview

This document explains the technical architecture, design decisions, and implementation details of the Hyperliquid Trader Address Tracker.

## System Components

### 1. Configuration Layer (`config.py`)

**Purpose**: Centralized configuration management using environment variables and Pydantic validation.

**Key Features**:
- Type-safe configuration using Pydantic models
- Environment-based configuration (`.env` file)
- Automatic API URL selection based on network (mainnet/testnet)
- Flexible coin selection (specific coins or all coins)

**Design Decision**: Using Pydantic provides runtime validation and clear error messages when configuration is invalid, preventing runtime errors.

### 2. Connection Manager (`connection.py`)

**Purpose**: Manages WebSocket connections to Hyperliquid using the official Python SDK.

**Key Features**:
- WebSocket connection management
- Multi-coin subscription handling
- Automatic reconnection (handled by SDK)
- Graceful disconnection

**Design Decision**: We use the official Hyperliquid SDK instead of raw WebSocket connections for:
- Built-in reconnection logic
- Proper message parsing
- API updates compatibility
- Reduced maintenance burden

### 3. Address Tracker (`address_tracker.py`)

**Purpose**: Core business logic for extracting addresses from trade events and managing batch processing.

**Key Features**:
- Thread-safe batch processing with locks
- In-memory deduplication within batches
- Trade volume calculation
- Statistics tracking per coin

**Design Decision**: Batch processing vs. real-time insertion:
- **Batch Wins**: At high trade volumes (1000+ trades/minute), individual INSERTs would cause database lock contention
- **Memory Efficient**: Deque-based queue keeps memory usage constant
- **Acceptable Latency**: 60-second batches are fine for address tracking (not HFT)

### 4. Storage Layer (`storage.py`)

**Purpose**: Database operations with SQLite for persistent address storage.

**Schema Design**:

```sql
-- Primary tracking table
addresses (
    address PRIMARY KEY,      -- Ethereum-style address
    first_seen TIMESTAMP,     -- When first observed
    last_seen TIMESTAMP,      -- Most recent activity
    trade_count INTEGER,      -- Number of trades
    total_volume_usd REAL     -- Cumulative trading volume
)

-- Phase 2 ready: Detailed trade history
trades (
    id PRIMARY KEY,
    address FOREIGN KEY,
    coin TEXT,
    side TEXT,
    price REAL,
    size REAL,
    value_usd REAL,
    trade_hash TEXT,
    trade_id INTEGER,
    timestamp TIMESTAMP
)
```

**Key Features**:
- Batch upsert with `ON CONFLICT` clause
- Indexed for fast queries
- Context manager for connection safety
- Statistics methods for dashboard

**Design Decision - SQLite vs. PostgreSQL**:

| Criteria | SQLite | PostgreSQL |
|----------|--------|------------|
| Setup | Zero config | Requires server |
| Performance (reads) | Excellent (embedded) | Excellent (network) |
| Performance (writes) | Good (10K+ inserts/sec) | Excellent (unlimited) |
| Concurrency | Single writer | Multiple writers |
| Scalability | Millions of rows | Billions of rows |
| Migration Path | Easy to export | - |

**Verdict**: SQLite is perfect for Phase 1 (single instance, <10M addresses). Easy migration to PostgreSQL for Phase 2 if needed.

### 5. Main Application (`main.py`)

**Purpose**: Orchestrates all components and manages application lifecycle.

**Architecture**:

```
Main Thread:
├── Initialize components
├── Connect to Hyperliquid
├── Subscribe to coins
├── Start periodic flush worker thread
└── Keep alive loop (blocking)

Worker Thread (daemon):
├── Sleep for DEDUP_INTERVAL seconds
├── Flush pending batch
├── Log statistics
└── Repeat
```

**Key Features**:
- Signal handling (SIGINT, SIGTERM) for graceful shutdown
- Thread-based periodic flushing
- Comprehensive logging
- Final statistics on exit

**Design Decision - Threading vs. Asyncio**:
- Hyperliquid SDK uses threading for WebSocket callbacks
- Mixing asyncio with SDK threading is complex
- Threading is simpler and sufficient for this use case
- Dashboard runs in separate daemon thread

### 6. Web Dashboard (`dashboard.py`)

**Purpose**: Real-time web interface for monitoring tracker statistics.

**Technology**: Flask + vanilla JavaScript (no frontend framework)

**Features**:
- Server-side rendered HTML with embedded CSS/JS
- REST API endpoints for statistics
- Auto-refresh every 5 seconds
- Responsive design (mobile-friendly)

**API Endpoints**:

```
GET /                      -> Dashboard HTML
GET /api/stats            -> Overall statistics
GET /api/addresses        -> Recent addresses
GET /api/top-traders      -> Top traders by volume/count
```

**Design Decision - Why Flask?**:
- Lightweight and fast
- Single-file dashboard possible
- No complex frontend build process
- Easy to extend with more endpoints

**Design Decision - Why No Frontend Framework?**:
- Simple dashboard doesn't need React/Vue complexity
- Faster initial load (no bundle)
- Easier to customize
- Can add framework later if needed

### 7. Utils (`utils.py`)

**Purpose**: Shared utilities for logging and formatting.

**Key Features**:
- Dual-output logging (console + file)
- Number formatting (1000 -> 1K, 1000000 -> 1M)
- Address shortening for display
- Uptime calculation

## Data Flow

```
Hyperliquid WebSocket
       ↓
[Trade Event: {users: [buyer, seller], ...}]
       ↓
Connection.subscribe() callback
       ↓
AddressTracker.process_trade_event()
       ↓
Extract addresses → Add to batch queue
       ↓
[Batch size reached OR 60s elapsed]
       ↓
AddressTracker.flush_batch()
       ↓
AddressStorage.batch_insert_addresses()
       ↓
SQLite Database (UPSERT with ON CONFLICT)
       ↓
Dashboard queries → Display statistics
```

## Concurrency & Thread Safety

### Thread Model

1. **Main Thread**: WebSocket event loop (managed by SDK)
2. **Worker Thread**: Periodic batch flushing
3. **Dashboard Thread**: Flask web server

### Synchronization

- **AddressTracker**: Uses `threading.Lock` for batch queue access
- **Database**: SQLite handles concurrent reads, single writer
- **No shared state** between threads except through AddressTracker

### Trade-offs

- **Pros**: Simple, predictable, no race conditions
- **Cons**: Limited by GIL for CPU-bound tasks (not an issue here)

## Performance Characteristics

### Memory Usage

```
Component              Memory
----------------------------------
Python interpreter     ~30 MB
Hyperliquid SDK       ~10 MB
Batch queue (1000)    ~0.2 MB
Flask dashboard       ~5 MB
SQLite connection     ~2 MB
----------------------------------
Total                 ~50 MB
```

### CPU Usage

- Idle: <1%
- Active (100 trades/sec): ~3-5%
- Database writes: Spike to ~10% during flush

### Network Usage

- Per coin: ~0.5-2 KB/s (WebSocket)
- 4 coins: ~2-8 KB/s total
- Dashboard: ~1 KB/5sec per client

### Database Growth

- ~100 bytes per address
- 10,000 addresses ≈ 1 MB
- 1,000,000 addresses ≈ 100 MB

## Error Handling & Recovery

### Connection Failures

- **WebSocket disconnect**: SDK automatically reconnects
- **API unavailable**: Logged, retries handled by SDK
- **Network issues**: Graceful degradation, local queue retained

### Database Errors

- **Lock timeout**: Retry with exponential backoff
- **Disk full**: Log error, continue tracking in memory
- **Corruption**: Detect on startup, backup and rebuild

### Application Crashes

- **SIGINT/SIGTERM**: Flush pending data, graceful exit
- **Unhandled exception**: Log stack trace, flush data, exit
- **Out of memory**: Batch size configurable, can reduce

## Security Considerations

### Data Privacy

- Addresses are public blockchain data (no PII)
- No authentication required for Hyperliquid API
- Dashboard accessible to localhost by default

### Input Validation

- Pydantic validates configuration
- SQL injection prevented (parameterized queries)
- No user input in WebSocket data processing

### Recommendations for Production

1. Add authentication to dashboard endpoints
2. Use HTTPS for dashboard (nginx proxy)
3. Rate limit API endpoints
4. Set up monitoring/alerting
5. Regular database backups

## Scalability Analysis

### Current Limits

- **Addresses**: 10M+ (SQLite limit ~281 TB)
- **Trades/sec**: ~1000 (batch processing bottleneck)
- **Concurrent coins**: 100+ (WebSocket subscriptions)

### Bottlenecks

1. **SQLite writes**: Single writer, ~10K inserts/sec
2. **Network**: WebSocket per coin (max ~1000 coins practical)
3. **Memory**: Batch queue size (configurable)

### Scaling Options

**Vertical (Single Machine)**:
- Increase batch size (reduces write frequency)
- Add more RAM (larger batches)
- Use SSD (faster SQLite writes)

**Horizontal (Multiple Machines)**:
- Split coins across instances
- Aggregate databases periodically
- Migrate to PostgreSQL for centralization

## Phase 2 Preparation

The architecture supports these extensions:

### 1. Trader Analytics
- `trades` table already captures detailed history
- Can calculate PnL, win rate, avg position size
- Add materialized views for performance

### 2. Pattern Detection
- Real-time trade analysis in callback
- Whale detection (large trades)
- Unusual activity alerts

### 3. API Extensions
```python
GET /api/trader/{address}     # Detailed trader profile
GET /api/analytics/volume     # Volume analytics
GET /api/alerts               # Real-time alerts
POST /api/watch/{address}     # Add to watchlist
```

### 4. Machine Learning
- Export trade data for model training
- Prediction API integration
- Feature engineering pipeline

## Testing Strategy

### Unit Tests
- Configuration loading
- Address extraction logic
- Database operations
- Utility functions

### Integration Tests
- WebSocket connection
- End-to-end trade processing
- Dashboard API endpoints

### Manual Testing
- Run on testnet first
- Verify data consistency
- Test graceful shutdown
- Monitor resource usage

## Deployment Options

### Development
```bash
python src/main.py
```

### Production (Systemd)
```ini
[Unit]
Description=Hyperliquid Tracker
After=network.target

[Service]
Type=simple
User=tracker
WorkingDirectory=/opt/hyper-tracker
ExecStart=/opt/hyper-tracker/venv/bin/python src/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "src/main.py"]
```

## Monitoring & Observability

### Logs
- Location: `logs/tracker.log`
- Rotation: Implement logrotate
- Levels: DEBUG, INFO, WARNING, ERROR

### Metrics to Track
- Trades processed per minute
- New addresses per hour
- Database size growth
- WebSocket reconnection count
- API response times

### Alerting Triggers
- WebSocket disconnected >5 minutes
- No new trades >10 minutes
- Database size >80% disk
- Memory usage >90%

## Future Improvements

### Performance
1. Connection pooling for database
2. Read replicas for dashboard queries
3. Redis cache for hot data
4. Async/await refactor

### Features
1. Historical data backfill
2. Export to CSV/JSON
3. Email/Telegram alerts
4. Admin panel for configuration
5. Multi-exchange support

### Infrastructure
1. Kubernetes deployment
2. Prometheus metrics
3. Grafana dashboards
4. ELK stack for logs

---

**Last Updated**: January 2025
**Version**: 1.0.0
