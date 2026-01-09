# Observer Dashboard

Sequential trader review and approval system for hyper-tracker.

## Overview

The Observer dashboard provides a comprehensive interface for manually reviewing and approving traders from the analyzed_traders database. It allows you to:

- Review traders one-by-one with complete metrics and live data
- View PnL timeline charts
- See current open positions from the API
- Approve or reject traders with optional reasons
- Filter by best (85-100) or worst (0-10) traders
- Navigate sequentially through the queue

## Features

- **Sequential Workflow**: Review traders one at a time with approve/reject actions
- **Score Range Filters**: Toggle between best traders (85-100), worst traders (0-10), or all traders
- **Live API Data**: Real-time positions and PnL data from Hyperliquid
- **PnL Visualization**: Chart.js timeline showing cumulative PnL
- **Approval Tracking**: Stores approved traders in `data/approved_traders.db`
- **Rejection Log**: Tracks rejected traders with optional reasons
- **Keyboard Shortcuts**: Fast navigation and actions via keyboard
- **Fabietti Design**: Brutalist, minimalist design system with 0.85px borders

## Installation

No additional dependencies required - uses the same requirements as the main project.

## Configuration

Configuration is stored in `observer/config/config.yaml`:

```yaml
api:
  base_url: "https://api.hyperliquid.xyz"
  rate_limit_calls: 20
  cache_ttl_seconds: 300

dashboard:
  host: "127.0.0.1"
  port: 5003

filters:
  best_traders_min_score: 85
  best_traders_max_score: 100
  worst_traders_min_score: 0
  worst_traders_max_score: 10
  default_view: "best"

review:
  enable_rejection_log: true
  auto_advance_after_action: true

logging:
  level: "INFO"
  file: "./logs/observer.log"
```

## Usage

### Start the Dashboard

```bash
cd observer
python3 main.py
```

The dashboard will be available at: http://127.0.0.1:5003

### Keyboard Shortcuts

- **Arrow Left/Right**: Navigate between traders
- **A**: Approve current trader
- **R**: Reject current trader
- **1**: Switch to best traders view (85-100)
- **2**: Switch to worst traders view (0-10)
- **3**: Switch to all traders view (0-100)

### Workflow

1. Dashboard loads with the default view (best traders by default)
2. View complete trader information:
   - All statistical metrics from the analyzer
   - PnL timeline chart
   - Current open positions (live from API)
   - Statistical analysis details
3. Review the trader data
4. Click **APPROVE** or **REJECT** (or use A/R keys)
5. Optionally add a reason for your decision
6. Dashboard automatically advances to the next trader
7. Continue reviewing until queue is complete

### Filter Modes

**Best Traders (85-100)**
- Focus on statistically good traders
- Use for finding profitable traders to follow

**Worst Traders (0-10)**
- Focus on statistically bad traders
- Use for contrarian strategies or traders to avoid

**All Traders (0-100)**
- Review all traders regardless of score

## Database Structure

### approved_traders.db

**approved_traders table**:
- Stores approved traders with full metrics snapshot
- Includes approval timestamp and optional reason
- Primary key: address

**rejected_traders table**:
- Logs rejected traders with rejection timestamp
- Includes optional rejection reason
- Allows same trader to be rejected multiple times (with history)

## API Endpoints

The dashboard provides the following REST API endpoints:

- `GET /` - Main dashboard HTML
- `GET /api/queue?min_score=X&max_score=Y` - Get filtered trader list
- `GET /api/trader/<address>` - Get complete trader data (DB + API)
- `POST /api/trader/<address>/approve` - Approve a trader
- `POST /api/trader/<address>/reject` - Reject a trader
- `GET /api/navigation/<address>/next` - Get next trader in queue
- `GET /api/navigation/<address>/previous` - Get previous trader
- `GET /api/stats` - Get approval statistics
- `GET /api/approved` - List all approved traders

## Directory Structure

```
observer/
├── main.py                 # Entry point
├── config/
│   └── config.yaml         # Configuration
├── core/
│   ├── config.py          # Config loader
│   ├── database.py        # Database operations
│   ├── trader_loader.py   # Queue management
│   └── live_data_fetcher.py  # API integration
├── dashboard/
│   ├── app.py             # Flask application
│   └── templates/
│       └── observer.html  # UI frontend
├── data/                  # Created at runtime
│   └── approved_traders.db
└── logs/                  # Created at runtime
    └── observer.log
```

## Integration with Other Modules

The Observer reads from:
- `data/analyzed_traders.db` - Phase 2 analyzer database (read-only)

The Observer writes to:
- `observer/data/approved_traders.db` - New database for approved traders

Other modules (like follower) can read from `approved_traders.db` to get curated trader lists.

## Notes

- The Observer never modifies the analyzer database
- API calls are cached for 5 minutes to respect rate limits
- Already reviewed traders are excluded from the queue
- You can re-review traders by switching filters or clearing the approved/rejected status manually

## Troubleshooting

**Dashboard won't start:**
- Check that `data/analyzed_traders.db` exists (run analyzer first)
- Verify config file at `observer/config/config.yaml`

**No traders in queue:**
- Check the score range filter
- Verify traders exist in that range in analyzed_traders.db
- Check if all traders are already approved/rejected

**API errors:**
- Check Hyperliquid API is accessible
- Verify rate limiting configuration
- Check network connectivity

## Example Session

```bash
# Start the dashboard
cd observer
python3 main.py

# Output:
# Observer Dashboard Starting
# Dashboard URL: http://127.0.0.1:5003
# Default View: best
#
# Keyboard Shortcuts:
#   - Arrow Keys: Navigate
#   - A: Approve
#   - R: Reject
#   - 1: Best traders view
#   - 2: Worst traders view
```

Open http://127.0.0.1:5003 in your browser and start reviewing!
