# Hyperliquid Trader Intelligence System

A comprehensive 4-phase system for identifying and profiting from consistently poor traders on Hyperliquid DEX through statistical analysis and contrarian trading strategies.

## System Overview

```
Phase 1: FETCHER          Phase 2: ANALYZER         Phase 3: CONTRARIAN       Phase 4: SIMULATOR
┌──────────────┐         ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ Live Trades  │────────▶│  Statistical │────────▶│   Position   │────────▶│ Paper Trading│
│   Monitor    │         │   Analysis   │         │  Monitoring  │         │   Execution  │
└──────────────┘         └──────────────┘         └──────────────┘         └──────────────┘
  WebSocket API           Bad Trader ID            Signal Generation         Portfolio Mgmt
  Address Tracking        Performance Scoring      Contrarian Logic          Live Rebalancing
  SQLite Storage          Monte Carlo Tests        Confidence Weighting      P&L Tracking
  Dashboard:5000          Dashboard:5001           Console Dashboard         Dashboard:5002
```

## Component Details

### Phase 1: Fetcher (`fetcher/`)
**Real-time trade monitoring and address collection**

**Core Functions:**
- WebSocket connection to Hyperliquid for live trade data
- Extracts buyer/seller addresses from all trades
- Tracks trading volume and frequency per address
- Stores in SQLite with deduplication and batch processing

**Key Features:**
- Configurable coin selection (specific coins or all pairs)
- Batch processing (configurable batch size, default 1000)
- Automatic reconnection handling
- Web dashboard with real-time statistics

**Configuration:** `.env` file
- `TRACK_ALL_COINS`: Monitor all coins or selected pairs
- `SELECTED_COINS`: Comma-separated coin list
- `BATCH_SIZE`: Addresses before flush
- `DASHBOARD_PORT`: Default 5000

**Database:** `fetcher/data/addresses.db`
- `addresses` table: Unique addresses with trade counts and volumes
- `trades` table: Complete trade history for analysis

**Usage:**
```bash
cd fetcher
python main.py
```

---

### Phase 2: Analyzer (`analyzer/`)
**Statistical analysis to identify consistently poor performers**

**Core Functions:**
- Read-only access to Phase 1 database
- Fetches complete trading history per address via Hyperliquid API
- Performs rigorous statistical testing (t-tests, Monte Carlo simulations)
- Scores traders 0-100 based on performance vs random chance
- Alerts on exceptionally bad traders (score ≤ 5, p < 0.01)

**Statistical Methods:**
- **One-sample t-test**: Tests if mean PnL significantly differs from zero
- **Monte Carlo simulation**: 1000 iterations comparing against random performance
- **Sharpe ratio**: Risk-adjusted returns
- **Expected value**: Long-term profit/loss expectation per trade

**Scoring System:**
- 0-5: Exceptionally bad (significantly worse than random) → ALERT
- 5-15: Very poor (likely worse than random)
- 15-40: Below average but not significant
- 40-60: Random performance
- 60-85: Above average
- 85-95: Very good
- 95-100: Exceptional

**Key Features:**
- Minimum 30 trades required for analysis
- Concurrent analysis of 10 traders (configurable)
- Re-analysis every 7 days for existing traders
- Separate database for isolation from Phase 1
- JSON alert logging for integration

**Configuration:** `analyzer/config/config.yaml`
- `min_trades`: Statistical significance threshold (default 30)
- `p_value_threshold`: Confidence level (default 0.01)
- `alert_score_threshold`: Alert trigger (default 5)
- `monte_carlo_iterations`: Simulation count (default 1000)

**Database:** `analyzer/data/analyzed_traders.db`
- `scored_traders` table: Performance metrics and statistical analysis
- `analysis_log` table: Tracking of all analysis attempts

**Usage:**
```bash
cd analyzer
python main.py --mode continuous  # Continuous monitoring
python main.py --mode once --limit 50  # One-time batch
```

---

### Phase 3: Contrarian (`contrarian/`)
**Real-time position monitoring and signal generation**

**Core Functions:**
- Identifies traders with score ≤ 5 from Phase 2
- Fetches current open positions from Hyperliquid API
- Aggregates positioning by trading pair
- Generates contrarian signals (opposite of bad trader positions)
- Calculates confidence scores based on consensus and sample size

**Signal Logic:**
- **STRONG SHORT**: 70%+ of bad traders are LONG
- **MODERATE SHORT**: 60-70% are LONG
- **STRONG LONG**: 70%+ are SHORT
- **MODERATE LONG**: 60-70% are SHORT
- **NEUTRAL**: 40-60% either way

**Confidence Calculation:**
```
Imbalance = abs(long_pct - 50%) / 50%
Sample factor = min(1.0, traders / (min_traders * 3))
Confidence = (imbalance * 0.7) + (sample_factor * 0.3)
```

**Key Features:**
- Dual metrics: count-based and size-weighted (USD value)
- Minimum 10 traders required for signal generation
- Rich console dashboard with live updates (90-second refresh)
- Historical signal storage for validation
- API rate limiting and concurrent request management

**Configuration:** `contrarian/config.json`
- `bad_trader_score_threshold`: Max score to consider (default 5)
- `min_traders_for_signal`: Minimum sample size (default 10)
- `signal_thresholds.strong`: Strong signal threshold (default 0.70)
- `update_interval_seconds`: Refresh rate (default 90)

**Database:** `contrarian/data/contrarian_signals.db`
- `contrarian_signals` table: All generated signals with metrics
- `position_snapshot` table: Individual trader positions

**Usage:**
```bash
python contrarian/main.py
```

---

### Phase 4: Simulator (`simulator/`)
**Paper trading simulator with automated execution**

**Core Functions:**
- Reads signals from Phase 3 database
- Manages virtual $100k portfolio
- Executes confidence-weighted position sizing
- Automatically rebalances every 15 minutes
- Tracks performance with comprehensive metrics

**Position Sizing:**
- Confidence-weighted allocation across top 10 signals
- Maximum 40% per position
- Minimum $1,000 trade size
- 100% capital deployment (no cash reserve)

**Realistic Execution:**
- Maker fee: 0.02%
- Taker fee: 0.05%
- Size-based slippage model
- Live price fetching every 5 seconds

**Performance Metrics:**
- Sharpe ratio (30-day rolling, annualized)
- Maximum drawdown
- Win rate and average win/loss
- Total P&L and returns
- Position-level unrealized P&L

**Key Features:**
- Real-time mark-to-market valuations
- Complete trade history with fees and slippage
- Web dashboard with equity curve and position breakdowns
- Automatic state saving and recovery
- Graceful shutdown handling

**Configuration:** `simulator/config.json`
- `portfolio.starting_capital`: Initial capital (default 100000)
- `strategy.rebalance_interval_seconds`: Rebalance frequency (default 900)
- `strategy.min_confidence_threshold`: Minimum signal confidence (default 0.60)
- `execution.taker_fee`: Trading fees (default 0.0005)

**Database:** `simulator/data/simulator.db`
- `positions` table: Current open positions
- `trades` table: Complete execution history
- `portfolio_state` table: Equity snapshots
- `performance_history` table: Time-series metrics
- `rebalance_history` table: Rebalancing events

**Usage:**
```bash
python simulator/main.py
```

**Dashboard:** http://localhost:5002
- Portfolio summary and P&L
- Performance metrics
- Equity curve chart
- Open positions table
- Position allocation pie chart
- Trade history

---

## Installation

### Prerequisites
- Python 3.8+
- pip package manager
- Internet connection for Hyperliquid API

### Setup
```bash
# Clone repository
cd hyper-tracker

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies (all phases)
pip install -r requirements.txt

# Configure Phase 1
cp .env.example .env
# Edit .env with your settings

# Configure Phase 2
# Edit analyzer/config/config.yaml if needed

# Configure Phase 3
# Edit contrarian/config.json if needed

# Configure Phase 4
# Edit simulator/config.json if needed
```

### Running the System

**Sequential startup (recommended for first time):**
```bash
# Terminal 1: Start Phase 1 (Fetcher)
cd fetcher && python main.py

# Wait 5-10 minutes for address collection

# Terminal 2: Start Phase 2 (Analyzer)
cd analyzer && python main.py --mode continuous

# Wait for bad trader identification

# Terminal 3: Start Phase 3 (Contrarian)
python contrarian/main.py

# Terminal 4: Start Phase 4 (Simulator)
python simulator/main.py
```

**Access Dashboards:**
- Phase 1: http://localhost:5000
- Phase 2: http://localhost:5001
- Phase 4: http://localhost:5002
- Phase 3: Terminal-based Rich dashboard

---

## System Architecture

### Data Flow
```
1. Fetcher collects addresses from live trades
   └─▶ addresses.db

2. Analyzer reads addresses, fetches trade history
   ├─▶ Performs statistical analysis
   └─▶ analyzed_traders.db (bad traders)

3. Contrarian reads bad traders, fetches positions
   ├─▶ Generates inverse signals
   └─▶ contrarian_signals.db

4. Simulator reads signals
   ├─▶ Executes paper trades
   └─▶ simulator.db (portfolio tracking)
```

### Isolation & Safety
- Each phase uses separate databases
- Phase 2+ only READ from prior phases
- No write conflicts between components
- Fault isolation: crashes don't cascade
- Each phase can run independently

### API Usage
All phases use Hyperliquid's public API:
- **Fetcher**: WebSocket trade subscriptions
- **Analyzer**: HTTP `userFills` endpoint
- **Contrarian**: HTTP `clearinghouseState` endpoint
- **Simulator**: HTTP `allMids` endpoint for prices

**Rate Limiting:**
- Analyzer: 20 req/sec, 10 concurrent
- Contrarian: 15 req/sec, 10 concurrent
- Simulator: 10 req/sec, 5 concurrent

---

## Performance Characteristics

### Resource Usage (per phase)
| Phase | CPU | Memory | Network | Disk Growth |
|-------|-----|--------|---------|-------------|
| Fetcher | <5% | ~50MB | 1-2KB/s per coin | ~1MB/10k addresses |
| Analyzer | 5-10% | ~150MB | 10-50KB/s | ~1MB/10k traders |
| Contrarian | <5% | ~50MB | Burst: 280 calls/90s | ~100KB/day |
| Simulator | <5% | ~150MB | 1-2KB/s | ~500KB/day |

### Throughput
- **Fetcher**: Real-time (all trades captured)
- **Analyzer**: ~100-200 traders/hour
- **Contrarian**: ~280 traders/90 seconds
- **Simulator**: Updates every 5s, rebalances every 15min

---

## Troubleshooting

### Phase 1 Issues
- **No trades appearing**: Verify coin selection, check WebSocket connection
- **Database errors**: Check write permissions in `data/` directory
- **Dashboard not loading**: Verify port 5000 is available

### Phase 2 Issues
- **Phase 1 database not found**: Ensure Fetcher has run and created addresses.db
- **API rate limit exceeded**: Reduce `concurrent_traders` in config
- **No addresses to analyze**: Wait for Fetcher to collect addresses

### Phase 3 Issues
- **No signals generated**: Normal if bad traders lack positions; lower `min_traders_for_signal`
- **No bad traders found**: Run Analyzer first to populate scored_traders table
- **API rate limit errors**: Reduce `api.concurrency_limit`

### Phase 4 Issues
- **No signals available**: Ensure Phase 3 is running and generating signals
- **Database not found**: Update `signals_db` path in config.json
- **Port already in use**: Change `dashboard.port` in config

---

## Project Structure

```
hyper-tracker/
├── fetcher/              # Phase 1: Real-time trade monitoring
│   ├── main.py
│   ├── config.py
│   ├── connection.py
│   ├── address_tracker.py
│   ├── storage.py
│   ├── dashboard.py
│   ├── data/
│   │   └── addresses.db
│   └── logs/
│
├── analyzer/             # Phase 2: Statistical analysis
│   ├── main.py
│   ├── config/
│   │   └── config.yaml
│   ├── core/
│   │   ├── api_client.py
│   │   ├── statistics.py
│   │   ├── database.py
│   │   └── config.py
│   ├── services/
│   │   ├── analyzer_service.py
│   │   └── alert_service.py
│   ├── dashboard/
│   │   └── app.py
│   ├── data/
│   │   └── analyzed_traders.db
│   └── logs/
│
├── contrarian/           # Phase 3: Signal generation
│   ├── main.py
│   ├── config.json
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── position_fetcher.py
│   │   ├── aggregator.py
│   │   ├── signal_generator.py
│   │   └── dashboard.py
│   ├── data/
│   │   └── contrarian_signals.db
│   └── logs/
│
├── simulator/            # Phase 4: Paper trading
│   ├── main.py
│   ├── config.json
│   ├── simulator.py
│   ├── signal_reader.py
│   ├── position_sizer.py
│   ├── price_fetcher.py
│   ├── order_executor.py
│   ├── portfolio_manager.py
│   ├── performance_tracker.py
│   ├── dashboard.py
│   ├── templates/
│   │   └── index.html
│   ├── data/
│   │   └── simulator.db
│   └── logs/
│
├── requirements.txt      # All dependencies
├── .env.example         # Phase 1 config template
└── README.md            # This file
```

---

## Design Philosophy

### Why This Architecture?

**Modular Independence:**
- Each phase solves one problem well
- Failures don't cascade
- Easy to test and debug individually
- Can run phases on different machines

**Progressive Analysis:**
- Raw data → Statistical analysis → Signal generation → Execution
- Each phase adds value to prior layer
- Clear separation of concerns

**Database Isolation:**
- No write conflicts
- Read-only dependencies
- Easy to backup/restore individual phases
- Scalable data architecture

**Statistical Rigor:**
- Not just tracking bad traders, but proving significance
- Monte Carlo validation against randomness
- 99% confidence threshold for alerts
- Multiple statistical tests for robustness

---

## Future Enhancements

### Phase 1 (Fetcher)
- Multi-exchange support
- Historical data backfill
- Advanced filtering (volume, trade size)

### Phase 2 (Analyzer)
- Machine learning for pattern detection
- Time-series analysis of trader behavior
- Correlation analysis between traders

### Phase 3 (Contrarian)
- Signal validation and backtesting
- WebSocket API for real-time signal delivery
- Discord/Telegram alert integration
- Web dashboard (HTML/JS)

### Phase 4 (Simulator)
- Multiple strategy support
- Risk management features (stop loss, max drawdown limits)
- Live trading integration (currently paper-only)
- Backtesting with historical data

---

## Disclaimer

This system is for educational and research purposes only. Paper trading results do not guarantee future performance. Cryptocurrency trading carries significant risk. Always conduct your own research and consult with financial professionals before trading with real capital.

The system identifies poor performers statistically but past performance does not predict future results. Use at your own risk.

---

## License

MIT License - See individual component READMEs for details.

## Support

For issues or questions:
1. Check component-specific logs
2. Review individual README files for each phase
3. Verify configuration files are correct
4. Ensure all prerequisites are met
5. Test API connectivity to Hyperliquid

---

**Built for Hyperliquid DEX | 4-Phase Statistical Trading System**
