# Architecture

How the modules fit together, what each one reads and writes, and the database
schemas.

## Data flow

```
Hyperliquid WebSocket
        │
        ▼
  pipeline/fetcher ─────────────▶ data/addresses.db
        every trade, both sides        addresses, trades
                                            │
                                            │ read-only
                                            ▼
                                   pipeline/analyzer ──▶ data/analyzed_traders.db
                                   fetches each trader's      scored_traders
                                   fills from the REST API    analysis_log
                                   and scores them            market_makers
                                            │
        ┌───────────────────┬───────────────┴───────────┬──────────────────┐
        │ read-only         │ read-only                 │ read-only        │ read-only
        ▼                   ▼                           ▼                  ▼
  pipeline/contrarian  pipeline/follower       pipeline/market_makers  pipeline/observer
  score <= 10          score >= 90             market_makers table     manual review UI
  invert the cohort    mirror the cohort       net delta               follow/invert/reject
        │                   │                           │                  │
        ▼                   ▼                           ▼                  ▼
  contrarian_signals.db follower_signals.db   mm_positions.db     approved_traders.db
        │                                                                (no consumer)
        │
        ├─────────────────────────────▶ research/simulator      (paper trading)
        │                                                        (superseded)
        └─────────────────────────────▶ research/execution_analyzer
                                         (offline analysis)
```

Every arrow after the fetcher is a read-only SQLite connection opened with
`file:...?mode=ro`. No module writes to another module's database, so they can
run concurrently and a crash in one does not corrupt another.

`approved_traders.db` and `mm_positions.db` are terminal — nothing downstream
reads them. The observer's follow/invert/reject decisions were meant to feed a
hand-curated portfolio that was never built.

## The modules

### `pipeline/fetcher`

Subscribes to Hyperliquid's WebSocket trade feed for the configured coins and
records the address on each fill. `TRACK_ROLE` decides whether the maker side,
the taker side, or both are recorded — taker-only is the useful setting, because
it excludes market makers, whose fill time is not their decision time.

Addresses are buffered (`BATCH_SIZE`, default 1000) and flushed in batches, with
a periodic deduplication pass. It also writes a `trades` table that nothing
downstream consumes: the analyzer re-fetches each trader's full history from the
REST API instead, because the WebSocket feed only sees trades from the moment
you connect.

Reconnects automatically. Serves a dashboard on :5000.

### `pipeline/analyzer`

Reads unanalyzed addresses from `addresses.db`, pulls each one's complete fill
history from the `userFills` endpoint, and computes a 0–100 score.

It skips traders with fewer than 30 trades, accounts younger than 10 days, and
balances under $500. Traders skipped for being too large or too active are
re-checked against the market-maker filters and recorded in the `market_makers`
table instead. Already-scored traders are refreshed every 7 days.

Concurrency is 3 with a 5 req/sec limit — both lowered from the original
values because Hyperliquid returns 429s above that. Throughput is roughly
100–200 traders/hour.

**The score does not mean what it says it means.** It was designed to test
whether a trader performs significantly worse than random; it is in practice a
profit/loss sign classifier. See
[`../pipeline/analyzer/README.md`](../pipeline/analyzer/README.md) for the
measurement and the three reasons it collapsed. The module is kept unchanged as
the baseline that a replacement had to beat.

Serves a dashboard on :5001.

### `pipeline/contrarian`

Every `update_interval_seconds`, fetches the current `clearinghouseState` for
every trader at or below the score threshold, aggregates their open positions by
coin, and emits the opposite of the cohort's net positioning.

Aggregation is dual: by trader count, and weighted by position value in USD.
`primary_metric` on each row records which drove the signal. A signal requires
at least `min_traders_for_signal` traders holding that coin.

Signal direction inverts the crowd — if 70%+ of the cohort is long, the signal
is STRONG SHORT. Confidence is `imbalance * sample_multiplier`, derived in
[CONFIDENCE_SCORE.md](CONFIDENCE_SCORE.md).

Renders a Rich console dashboard in its own terminal, serves a web dashboard on
:5002, and optionally pushes signal changes to Telegram.

### `pipeline/follower`

The same module with the comparison operator flipped: `score >= 90` instead of
`score <= 10`, and the cohort's direction passed through rather than inverted.
It is 95% byte-identical to `contrarian` — see
[`../pipeline/follower/README.md`](../pipeline/follower/README.md) for what the
other 5% is.

### `pipeline/market_makers`

Reads the `market_makers` table rather than `scored_traders`, filters to
accounts above $50k balance, and tracks their collective net delta per asset,
classifying it as BULLISH / BEARISH / NEUTRAL against configurable thresholds.

Market makers move funds between wallets, so the roster goes stale; the module
needs the fetcher running alongside it to keep discovering new ones.

### `pipeline/observer`

A Flask UI for reviewing traders one at a time — metrics, a cumulative PnL
chart, and live open positions — and recording a follow / invert / reject
decision. Built to sanity-check the analyzer's scoring by hand.

It is the only module that resolves its database paths to absolute paths, so it
runs correctly from any working directory.

### `research/execution_analyzer`

The offline analysis that answered the project's actual question. Scores traders
on execution timing rather than PnL, tests the result against a pre-registered
gate, and separately tests whether trader performance persists at all.

It reads from a local cache of fills rather than hitting the API, so
`persistence.py` and `cohort_alpha_check.py` reproduce their published numbers
with no network access. See
[`../research/execution_analyzer/README.md`](../research/execution_analyzer/README.md).

### `research/simulator`

Paper-trades the contrarian signals against live prices. Superseded by
`research/notebooks/`, and its Sharpe ratio calculation is wrong — see
[`../research/simulator/README.md`](../research/simulator/README.md).

## Schemas

### `data/addresses.db`

**`addresses`** — one row per unique address seen on the trade feed.

| column | type | |
|---|---|---|
| `address` | TEXT | primary key |
| `first_seen`, `last_seen` | TIMESTAMP | |
| `trade_count` | INTEGER | fills observed since tracking began |
| `total_volume_usd` | REAL | |

**`trades`** — raw fills as they arrived. Written but never read; the analyzer
re-fetches full history from the API.

### `data/analyzed_traders.db`

**`scored_traders`** — one row per analyzed trader.

| column | type | |
|---|---|---|
| `trader_id` | INTEGER | autoincrement primary key |
| `address` | TEXT | unique |
| `score` | INTEGER | 0–100, constrained |
| `total_pnl`, `mean_pnl_per_trade`, `std_dev` | REAL | from `closedPnl`, unnormalized dollars |
| `sharpe_ratio` | REAL | **wrong**: `(mean/std)*sqrt(250)` on per-*fill* PnL, as if each fill were a trading day |
| `expected_value`, `t_statistic`, `p_value`, `monte_carlo_percentile` | REAL | `monte_carlo_percentile` is a monotone function of `t_statistic` |
| `num_trades` | INTEGER | >= 30, constrained |
| `win_rate`, `avg_win`, `avg_loss` | REAL | opening fills carry `closedPnl = 0` and are counted, which depresses `win_rate` |
| `account_balance` | REAL | |
| `first_trade_time` | INTEGER | ms epoch |
| `last_analyzed` | TIMESTAMP | drives the 7-day refresh |
| `is_statistically_bad` | BOOLEAN | |

**`analysis_log`** — one row per attempt: `address`, `timestamp`, `status`,
`error_message`, `trades_fetched`. Useful for telling "skipped" apart from
"failed".

**`market_makers`** — `address`, `trade_count`, `account_balance`,
`first_trade_time`, `first_trade_age_hours`, `total_volume_usd`,
`first_detected`, `last_seen`, `detection_count`.

### `data/contrarian_signals.db`

**`contrarian_signals`** — one row per coin per sweep.

| column | |
|---|---|
| `timestamp`, `coin` | |
| `signal_direction` | `LONG` / `SHORT` / `NEUTRAL` |
| `signal_strength` | `STRONG` / `MODERATE` / `WEAK` / `NONE` |
| `bad_traders_total`, `long_count`, `short_count` | count-based aggregation |
| `long_percentage`, `short_percentage` | |
| `long_usd_value`, `short_usd_value`, `long_usd_percentage`, `short_usd_percentage` | size-weighted aggregation |
| `confidence_score` | `imbalance * sample_multiplier` |
| `primary_metric` | `count` or `size` — which drove the signal |
| `current_price` | added later; NULL on early rows |

**`position_snapshot`** — the individual positions behind each signal:
`timestamp`, `address`, `coin`, `side`, `size`, `position_value_usd`,
`entry_price`, `leverage_value`, `unrealized_pnl`. This is the table
`research/execution_analyzer/wallet_clusters.py` mines to detect multi-wallet
entities.

`data/follower_signals.db` mirrors this with a `follower_signals` table, minus
`current_price`.

### `data/mm_positions.db`

`position_snapshots`, `bias_history`, `mm_activity`. Retention is configurable:
7 days of snapshots, 30 days of bias history.

### `data/approved_traders.db`

`approved_traders` (with the follow/invert/reject flag) and `rejected_traders`
(with an optional reason).

## Design notes

**Why separate databases.** Each module owns exactly one, and reads everything
else read-only. No write contention, no cross-module transactions, and any
module can be deleted without breaking the others.

**Why SQLite.** Single-writer is sufficient — each database has exactly one
writer by construction. The largest, `contrarian_signals.db`, reached 1.6GB and
189,024 signal rows without trouble.

**Why the analyzer re-fetches history.** The WebSocket feed only sees trades
from the moment you connect, so the `trades` table cannot support a
retrospective analysis. The `userFills` endpoint returns a trader's full
history.

**Why the timestamps are Europe/Rome.** Display only, and configurable per
module. Storage is UTC throughout.
