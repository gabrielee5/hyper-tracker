# Phase 3: Contrarian Signal System - Technical Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COMPLETE SYSTEM ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐      ┌──────────────┐      ┌─────────────────┐  │
│  │   Phase 1    │      │   Phase 2    │      │    Phase 3      │  │
│  │ Trade Tracker│ ───> │   Analyzer   │ ───> │ Contrarian      │  │
│  │              │      │              │      │ Signal System   │  │
│  └──────────────┘      └──────────────┘      └─────────────────┘  │
│        │                      │                        │           │
│        ↓                      ↓                        ↓           │
│  addresses.db         analyzed_traders.db    contrarian_signals.db│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Phase 3 Internal Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                  Phase 3: Contrarian Engine                    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                   Main Orchestrator                      │  │
│  │                    (main.py)                             │  │
│  └──────────────┬───────────────────────┬──────────────────┘  │
│                 │                       │                      │
│                 ↓                       ↓                      │
│  ┌──────────────────────┐    ┌─────────────────────┐         │
│  │  Configuration       │    │  Database Layer     │         │
│  │  - config.json       │    │  - Phase2Reader     │         │
│  │  - ConrarianConfig   │    │  - ContrarianDB     │         │
│  └──────────────────────┘    └─────────────────────┘         │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              Core Processing Pipeline                    │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │                                                          │  │
│  │  1. Query Bad Traders                                   │  │
│  │     ↓                                                    │  │
│  │     [Phase2Reader] → Get traders with score <= 5        │  │
│  │                                                          │  │
│  │  2. Fetch Positions                                     │  │
│  │     ↓                                                    │  │
│  │     [PositionFetcher] → Hyperliquid API                 │  │
│  │     │                                                    │  │
│  │     └─> clearinghouseState endpoint                     │  │
│  │         Rate limited (15/sec)                           │  │
│  │         Concurrent batching (10 at a time)              │  │
│  │                                                          │  │
│  │  3. Parse & Aggregate                                   │  │
│  │     ↓                                                    │  │
│  │     [Parser] → Extract coin, side, size, value          │  │
│  │     ↓                                                    │  │
│  │     [Aggregator] → Group by coin                        │  │
│  │     │                                                    │  │
│  │     ├─> Count-based metrics (# traders)                 │  │
│  │     └─> Size-weighted metrics (USD value)               │  │
│  │                                                          │  │
│  │  4. Generate Signals                                    │  │
│  │     ↓                                                    │  │
│  │     [SignalGenerator]                                   │  │
│  │     │                                                    │  │
│  │     ├─> Apply contrarian logic                          │  │
│  │     ├─> Classify strength (STRONG/MODERATE)             │  │
│  │     └─> Calculate confidence score                      │  │
│  │                                                          │  │
│  │  5. Output & Store                                      │  │
│  │     ↓                                                    │  │
│  │     ├─> [Dashboard] Display in terminal                 │  │
│  │     └─> [Database] Save to contrarian_signals.db        │  │
│  │                                                          │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          DATA FLOW                               │
└─────────────────────────────────────────────────────────────────┘

Phase 2 DB                    Hyperliquid API
    │                               │
    │ Query bad traders            │ Fetch positions
    │ (score <= 5)                 │ (clearinghouseState)
    ↓                               ↓
┌──────────────┐              ┌──────────────┐
│ 277 addresses│              │ Position data│
└───────┬──────┘              └──────┬───────┘
        │                            │
        └────────────┬───────────────┘
                     ↓
            ┌────────────────┐
            │ Parse Positions│
            │ - coin: BTC    │
            │ - side: LONG   │
            │ - size: 0.5    │
            │ - value: $22.5K│
            └────────┬───────┘
                     ↓
            ┌────────────────┐
            │   Aggregate    │
            │   by Coin      │
            └────────┬───────┘
                     ↓
        ┌────────────────────────────┐
        │  BTC: 45 traders           │
        │  - Long: 37 (82%)          │
        │  - Short: 8 (18%)          │
        │  - Long USD: $890K         │
        │  - Short USD: $180K        │
        └────────────┬───────────────┘
                     ↓
        ┌────────────────────────────┐
        │  Generate Signal           │
        │  82% long > 70% threshold  │
        │  → STRONG SHORT signal     │
        │  → Confidence: 0.85        │
        └────────────┬───────────────┘
                     ↓
        ┌────────────┴───────────────┐
        ↓                            ↓
┌───────────────┐          ┌─────────────────┐
│   Dashboard   │          │  Database Save  │
│   Display     │          │  - Signal       │
│   (Terminal)  │          │  - Snapshot     │
└───────────────┘          └─────────────────┘
```

## Module Interactions

```
┌─────────────────────────────────────────────────────────────────┐
│                      MODULE RELATIONSHIPS                        │
└─────────────────────────────────────────────────────────────────┘

main.py (ContrarianEngine)
    │
    ├─── imports ───> config.py (ConrarianConfig)
    │                     │
    │                     └─── loads ───> config.json
    │
    ├─── imports ───> database.py
    │                     │
    │                     ├─── Phase2Reader
    │                     │        │
    │                     │        └─── reads ───> analyzed_traders.db
    │                     │
    │                     └─── ContrarianDatabase
    │                              │
    │                              └─── writes ─> contrarian_signals.db
    │
    ├─── imports ───> position_fetcher.py
    │                     │
    │                     ├─── HyperliquidPositionFetcher
    │                     │        │
    │                     │        └─── API calls ─> api.hyperliquid.xyz
    │                     │
    │                     └─── parse_positions()
    │
    ├─── imports ───> aggregator.py (PositionAggregator)
    │                     │
    │                     └─── aggregate_positions()
    │                              │
    │                              └─── returns aggregated metrics
    │
    ├─── imports ───> signal_generator.py (ContrarianSignalGenerator)
    │                     │
    │                     ├─── generate_signals()
    │                     └─── calculate_confidence()
    │
    └─── imports ───> dashboard.py (ContrarianDashboard)
                          │
                          └─── render() / print_static()
```

## Class Architecture

### 1. Configuration Layer

```python
class ConrarianConfig:
    - bad_trader_score_threshold: int
    - min_traders_for_signal: int
    - update_interval_seconds: int
    - signal_thresholds: SignalThresholds
    - api: APIConfig
    - database: DatabaseConfig
    - dashboard: DashboardConfig

    + load()
    + save()
```

### 2. Database Layer

```python
class Phase2Reader:
    - db_path: Path

    + get_bad_traders(threshold) -> List[Dict]
    + get_trader_count(threshold) -> int

class ContrarianDatabase:
    - db_path: Path

    + initialize()
    + save_signal(signal: Dict)
    + save_position_snapshot(positions: List[Dict])
    + get_recent_signals(coin, limit) -> List[Dict]
    + get_signal_statistics(coin) -> Dict
```

### 3. API Layer

```python
class HyperliquidPositionFetcher:
    - base_url: str
    - rate_limiter: AsyncLimiter
    - session: aiohttp.ClientSession

    + fetch_positions(address) -> Dict
    + batch_fetch_positions(addresses) -> Dict[str, Dict]

def parse_positions(user_state: Dict) -> List[Dict]:
    # Converts API response to normalized format
```

### 4. Processing Layer

```python
class PositionAggregator:
    - min_traders_for_signal: int

    + aggregate_positions(positions) -> Dict[coin, metrics]
    + get_top_coins_by_activity(aggregated) -> List[Dict]
    + calculate_imbalance_score(aggregated_coin) -> float

class ContrarianSignalGenerator:
    - thresholds: SignalThresholds
    - min_traders_for_signal: int

    + generate_signals(aggregated) -> List[Dict]
    + generate_signal_for_coin(aggregated_coin) -> Dict
    + calculate_confidence(long_pct, short_pct, total) -> float
```

### 5. Display Layer

```python
class ContrarianDashboard:
    - console: Console
    - show_size_weighted: bool
    - top_signals_limit: int

    + render(signals, ...) -> Layout
    + print_static(signals, ...)
    + print_summary(signals)
```

### 6. Orchestration Layer

```python
class ContrarianEngine:
    - config: ConrarianConfig
    - phase2_reader: Phase2Reader
    - contrarian_db: ContrarianDatabase
    - position_fetcher: HyperliquidPositionFetcher
    - aggregator: PositionAggregator
    - signal_generator: ContrarianSignalGenerator
    - dashboard: ContrarianDashboard

    + initialize()
    + run_once() -> bool
    + run_continuous()
    + cleanup()
```

## Async Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ASYNC EXECUTION TIMELINE                      │
└─────────────────────────────────────────────────────────────────┘

T=0s    Start Cycle
        │
T=0.1s  └─> Query Phase 2 DB (277 addresses)
        │   ✓ Complete
        │
T=0.2s  └─> Batch Fetch Positions (concurrent)
        │   ├─> Request 1-10   (addresses 1-10)
        │   ├─> Request 11-20  (addresses 11-20)
        │   ├─> Request 21-30  (addresses 21-30)
        │   ...
        │   └─> Request 271-277 (addresses 271-277)
        │
        │   [Concurrent execution with rate limiting]
        │   [Max 10 concurrent, 15 calls/sec]
        │
T=18s   │   ✓ All positions fetched
        │
T=18.1s └─> Parse positions (fast, in-memory)
        │   ✓ Complete
        │
T=18.2s └─> Aggregate by coin (fast, in-memory)
        │   ✓ Complete
        │
T=18.3s └─> Generate signals (fast, in-memory)
        │   ✓ Complete
        │
T=18.4s └─> Save to database (async write)
        │   ✓ Complete
        │
T=18.5s └─> Render dashboard (fast, terminal output)
        │   ✓ Complete
        │
T=18.6s Cycle complete
        │
        └─> Sleep for 90s
        │
T=108.6s Start next cycle...

Total cycle time: ~20 seconds (fetch) + 1 second (processing)
Wait time: 90 seconds (configurable)
```

## Error Handling Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                      ERROR HANDLING FLOW                         │
└─────────────────────────────────────────────────────────────────┘

API Call Error
    │
    ├─ 429 (Rate Limit)
    │  └─> Activate circuit breaker (30s cooldown)
    │  └─> Retry after cooldown
    │
    ├─ Network Error
    │  └─> Exponential backoff (2^attempt seconds)
    │  └─> Max 3 retries
    │  └─> If all fail: skip trader, continue with others
    │
    ├─ Invalid Response
    │  └─> Log error
    │  └─> Skip trader
    │
    └─ Timeout
       └─> Retry with same backoff strategy

Database Error
    │
    ├─ Phase 2 DB not found
    │  └─> Fatal error, exit with message
    │
    ├─ Contrarian DB error
    │  └─> Create database
    │  └─> Initialize schema
    │
    └─ Write error
       └─> Log error
       └─> Continue (don't crash system)

Processing Error
    │
    ├─ Invalid position data
    │  └─> Skip position
    │  └─> Log warning
    │
    ├─ Aggregation error
    │  └─> Skip coin
    │  └─> Log error
    │
    └─> Signal generation error
        └─> Skip signal
        └─> Log error
        └─> Continue with other signals

Graceful Shutdown
    │
    └─> SIGINT/SIGTERM received
        └─> Set running = False
        └─> Complete current cycle
        └─> Close API session
        └─> Close database connections
        └─> Exit cleanly
```

## Performance Optimizations

### 1. Concurrent Position Fetching
```python
# Instead of:
for address in addresses:
    position = await fetch_position(address)  # Serial, slow

# We use:
await asyncio.gather(*[
    fetch_position(addr) for addr in addresses
])  # Concurrent, fast
```

### 2. Rate Limiting
```python
# AsyncLimiter ensures we don't exceed API limits
async with rate_limiter:  # Max 15/second
    await api_call()
```

### 3. Database Indexing
```sql
-- Fast lookups by coin and timestamp
CREATE INDEX idx_signals_coin_time ON contrarian_signals(coin, timestamp);
```

### 4. In-Memory Processing
```python
# Aggregation and signal generation happen in memory
# No database reads during processing
# Only write final results
```

## Security Considerations

### 1. Read-Only Phase 2 Access
```python
# Opens in read-only mode to prevent accidental writes
uri = f"file:{db_path}?mode=ro"
conn = await aiosqlite.connect(uri, uri=True)
```

### 2. Input Validation
```python
def _is_valid_address(self, address: str) -> bool:
    # Validates Ethereum address format
    # Prevents injection attacks
```

### 3. API Error Handling
```python
# Never exposes sensitive data in logs
logger.error(f"Error for {shorten_address(addr)}")
# Not: logger.error(f"Error for {full_address}")
```

### 4. Configuration Validation
```python
# Validates all config values
# Provides safe defaults
# Prevents invalid thresholds
```

## Scalability Analysis

### Current Limits
- **Traders:** 1000 (limited by API rate limits)
- **Update frequency:** Minimum 60 seconds
- **Memory:** ~100MB for 1000 traders
- **Database:** ~1MB per day of signals

### Bottlenecks
1. **API rate limits** (15 calls/sec)
2. **Network latency** (external API)
3. **SQLite writes** (not an issue for this scale)

### Scale-Up Strategy
1. **More traders:** Add API key rotation
2. **Faster updates:** Multiple API accounts
3. **More data:** Switch to PostgreSQL
4. **Real-time:** Add WebSocket support

## Testing Strategy

### Unit Tests
- Config loading/validation
- Position parsing
- Aggregation calculations
- Signal generation logic
- Confidence score calculation

### Integration Tests
- Phase 2 database reading
- API fetching (with mocks)
- End-to-end pipeline
- Dashboard rendering

### System Tests
- Full cycle with real data
- Error recovery
- Performance under load
- Long-running stability

---

This architecture provides:
- ✅ **Modularity:** Each component has clear responsibility
- ✅ **Testability:** All components can be tested independently
- ✅ **Scalability:** Can grow with demand
- ✅ **Maintainability:** Clean separation of concerns
- ✅ **Reliability:** Comprehensive error handling
- ✅ **Performance:** Optimized for speed and efficiency
