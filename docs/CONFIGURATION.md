# Configuration

Every setting in the project, where it lives, and what it actually does.

Each module keeps its own config next to its code, in whichever format that
module happened to be written with. There is no shared config layer.

| module | config file | format |
|---|---|---|
| `pipeline/fetcher` | root `.env` | env vars |
| `pipeline/analyzer` | `pipeline/analyzer/config/config.yaml` | YAML |
| `pipeline/contrarian` | `pipeline/contrarian/config.json` (+ `pipeline/contrarian/.env` for Telegram) | JSON |
| `pipeline/follower` | `pipeline/follower/config.json` | JSON |
| `pipeline/market_makers` | `pipeline/market_makers/config.json` | JSON |
| `pipeline/observer` | `pipeline/observer/config/config.yaml` | YAML |
| `research/simulator` | `research/simulator/config.json`, `config_three_asset.json` | JSON |

## Where the data lives

All databases are in the repo-root `data/`, all logs in the repo-root `logs/`,
all CSV exports in the repo-root `exports/`. All three are gitignored — a fresh
clone has no data and every module creates its own database on first run.

Configs refer to these with paths relative to the module directory, so they
read `../../data/...`. **A module must be started from its own directory** for
these to resolve. `contrarian`, `follower` and `simulator` `os.chdir` to their
own directory on startup and so work from anywhere; `fetcher`, `analyzer`,
`market_makers` and `observer` do not.

| database | written by | read by |
|---|---|---|
| `data/addresses.db` | `pipeline/fetcher` | `pipeline/analyzer` (read-only) |
| `data/analyzed_traders.db` | `pipeline/analyzer` | `contrarian`, `follower`, `market_makers`, `observer`, `research/execution_analyzer` (all read-only) |
| `data/contrarian_signals.db` | `pipeline/contrarian` | `research/simulator`, `research/execution_analyzer` |
| `data/follower_signals.db` | `pipeline/follower` | — |
| `data/mm_positions.db` | `pipeline/market_makers` | — |
| `data/approved_traders.db` | `pipeline/observer` | — |
| `data/simulator.db`, `data/simulator_three_asset.db` | `research/simulator` | — |

`approved_traders.db` and `mm_positions.db` have no consumers. The
follow/invert/reject decisions the observer UI records are never read back by
anything.

### How long each stage takes to fill

- **fetcher** — real-time, but the address pool is only useful after hours of
  running. The reference dataset (114,487 addresses) accumulated over months at
  15 minutes per hour.
- **analyzer** — roughly 100–200 traders/hour under the configured rate limits.
  6,911 traders were scored over the life of the project.
- **contrarian / follower** — one snapshot per `update_interval_seconds`,
  covering every trader past the score threshold.
- **`research/execution_analyzer/fetch_data.py`** — about 50 minutes for 2,548
  traders, resumable, producing a 242MB cache.

## `pipeline/fetcher` — root `.env`

Copy `.env.example` to `.env`. The defaults work.

| variable | default | meaning |
|---|---|---|
| `NETWORK` | `mainnet` | `mainnet` or `testnet`; selects the API URL |
| `TRACK_ALL_COINS` | `false` | subscribe to every listed perp rather than a list |
| `SELECTED_COINS` | `BTC,ETH,SOL,ARB` | which coins to subscribe to; ignored when `TRACK_ALL_COINS=true` |
| `TRACK_ROLE` | `both` | **deprecated, ignored.** Validated on startup, then unused — both addresses are always recorded. See [TRACK_ROLE_GUIDE.md](TRACK_ROLE_GUIDE.md) |
| `DATABASE_PATH` | `../../data/addresses.db` | relative to `pipeline/fetcher/` |
| `BATCH_SIZE` | `1000` | addresses buffered before a batch insert |
| `DEDUP_INTERVAL` | `60` | seconds between deduplication passes |
| `DASHBOARD_ENABLED` | `true` | serve the web dashboard |
| `DASHBOARD_PORT` | `5000` | |
| `DASHBOARD_HOST` | `0.0.0.0` | |
| `LOG_LEVEL` | `INFO` | |
| `LOG_FILE` | `logs/tracker.log` | |

`TRACK_ROLE` does nothing. The public `trades` subscription does not include the
`crossed` field needed to tell taker from maker, so the fetcher records both
addresses regardless of the setting. Taker-only filtering happens downstream in
`research/execution_analyzer/`, which reads `userFills` instead.

## `pipeline/analyzer` — `config/config.yaml`

**`analysis`** — what qualifies a trader and how they are judged.

| key | default | meaning |
|---|---|---|
| `min_trades` | `30` | trades required before a trader is scored at all |
| `p_value_threshold` | `0.01` | significance level for the t-test |
| `alert_score_threshold` | `5` | score at or below which an alert is logged |
| `monte_carlo_iterations` | `1000` | draws per trader |
| `reanalysis_interval_days` | `7` | how often an already-scored trader is refreshed |
| `min_first_trade_age_days` | `10` | ignore accounts younger than this |
| `min_account_balance` | `500` | USD floor for inclusion |

The score these produce is a PnL-sign classifier rather than the test against
random it was designed to be — `monte_carlo_iterations` in particular buys you
nothing, because the simulation re-encodes the t-statistic. See
[`pipeline/analyzer/README.md`](../pipeline/analyzer/README.md).

**`processing`** — `concurrent_traders` (3) and `batch_processing_interval`
(300s). Both were lowered from their original values because Hyperliquid
returns 429s at the original rate; `api.retry_delay_on_429` (30s) is the backoff.

**`api`** — `rate_limit_calls` (5/sec), `timeout` (10s), `max_retries` (3).

## `pipeline/contrarian` — `config.json`

| key | default | meaning |
|---|---|---|
| `bad_trader_score_threshold` | `10` | consider traders with `score <= this` |
| `min_traders_for_signal` | `10` | minimum cohort size before a signal is emitted |
| `signal_thresholds.strong` | `0.70` | cohort share on one side for a STRONG signal |
| `signal_thresholds.moderate` | `0.50` | cohort share for a MODERATE signal |
| `update_interval_seconds` | `1800` | seconds between position sweeps |
| `dashboard.refresh_rate` | `5` | console dashboard redraw, seconds |
| `dashboard.top_signals_limit` | `15` | rows shown |
| `dashboard.priority_coins` | `["BTC","ETH","SOL"]` | pinned to the top of the dashboard regardless of signal strength, so the coins you care about stay visible when a long tail of alts outranks them |
| `dashboard.timezone` | `Europe/Rome` | display only |
| `telegram.enabled` | `true` | send signal changes to Telegram |
| `telegram.watched_coins` | `["BTC","ETH","SOL"]` | which coins trigger a message |

Signal direction inverts the cohort: if `>= 70%` of the cohort is long, the
signal is `STRONG SHORT`. Between the moderate and strong thresholds it is
`MODERATE`; inside the neutral band it is `NEUTRAL`. Confidence is
`imbalance * sample_multiplier` — see
[CONFIDENCE_SCORE.md](CONFIDENCE_SCORE.md) for the derivation.

Note `moderate` is `0.50`, not `0.60`. At `0.50` the moderate band has zero
width on the majority side, so effectively every non-neutral reading is a
signal in the direction of the cohort majority.

### Telegram

`pipeline/contrarian/.env`, which is gitignored. Copy from
`pipeline/contrarian/.env.example`:

```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Leave them empty, or set `telegram.enabled` to `false`, to run without it.

## `pipeline/follower` — `config.json`

Identical to contrarian's except:

| key | default |
|---|---|
| `good_trader_score_threshold` | `90` (traders with `score >= this`) |
| `database.follower_path` | `../../data/follower_signals.db` |

No `telegram` block. The module is otherwise a copy of contrarian with the
comparison operator and the signal mapping flipped.

## `pipeline/market_makers` — `config.json`

| key | default | meaning |
|---|---|---|
| `analyzer_db_path` | `../../data/analyzed_traders.db` | source, reads the `market_makers` table |
| `local_db_path` | `../../data/mm_positions.db` | output |
| `monitoring.min_mm_balance` | `50000` | USD floor for an account to count as a market maker |
| `monitoring.fetch_interval_seconds` | `900` | seconds between position sweeps |
| `monitoring.min_position_value_usd` | `100` | ignore dust positions |
| `bias_analysis.neutral_threshold_percent` | `10` | net delta below this reads as NEUTRAL |
| `bias_analysis.strong_bias_threshold_percent` | `30` | net delta above this reads as strongly directional |
| `dashboard.port` | `5003` | |

The `market_makers` table is populated by the analyzer: when a trader is skipped
for being too large or too active to score meaningfully, it is re-checked
against the market-maker filters and recorded there instead.

## `pipeline/observer` — `config/config.yaml`

| key | default |
|---|---|
| `dashboard.host` | `127.0.0.1` |
| `dashboard.port` | `5006` |
| `filters.best_traders_min_score` | `85` |
| `filters.worst_traders_max_score` | `10` |
| `filters.default_view` | `best` |
| `api.cache_ttl_seconds` | `300` |

This is the only module that resolves its database paths to absolute paths
relative to its own directory, so it runs correctly from any working directory.

## `research/simulator` — `config.json`

| key | default |
|---|---|
| `portfolio.starting_capital` | `100000` |
| `strategy.rebalance_interval_seconds` | `1800` |
| `strategy.min_confidence_threshold` | `0.50` |
| `strategy.max_positions` | `10` |
| `portfolio.max_position_pct` | `0.40` |
| `execution.maker_fee` / `taker_fee` | `0.0002` / `0.0005` |
| `dashboard.port` | `5007` (`config_three_asset.json`: `5004`) |

The two configs drive two different allocators — see
[`research/simulator/STRATEGY_GUIDE.md`](../research/simulator/STRATEGY_GUIDE.md).
The module's reported Sharpe ratio is wrong; see
[`research/simulator/README.md`](../research/simulator/README.md).

## Ports

| port | module |
|---|---|
| 5000 | `pipeline/fetcher` |
| 5001 | `pipeline/analyzer` |
| 5002 | `pipeline/contrarian` |
| 5003 | `pipeline/market_makers` |
| 5004 | `research/simulator` (three-asset) |
| 5005 | `pipeline/follower` |
| 5006 | `pipeline/observer` |
| 5007 | `research/simulator` |

`contrarian` and `follower` set their port as a default argument in
`core/web_dashboard.py` rather than reading it from `config.json`.
