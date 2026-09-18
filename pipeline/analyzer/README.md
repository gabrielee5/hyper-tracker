# analyzer

Fetches each trader's full fill history from Hyperliquid and assigns a 0–100
score.

> **The score does not test what it says it tests.** It was designed to answer
> "is this trader significantly worse than random?" It is in practice a
> profit/loss sign classifier. The module is kept running and unchanged as the
> baseline a replacement had to beat — but do not build on `score` without
> reading the next section.

## Measured behaviour (2026-09-18)

Across 6,911 scored traders in `data/analyzed_traders.db`:

| group | `total_pnl < 0` | `total_pnl >= 0` |
|---|---|---|
| `score <= 5` | **1723** | **0** |
| `score >= 95` | **0** | **1284** |

Perfect separation in both directions. Three reasons it collapsed to that:

1. **The Monte Carlo adds nothing.** `_run_monte_carlo_simulation` draws
   `N(0, the trader's own sigma)`, so the percentile of the trader's mean within
   those draws is a monotone function of `mean/(sigma/sqrt(n))` — the
   t-statistic computed three lines earlier in `core/statistics.py`. It is one
   test reported twice, and `monte_carlo_iterations` buys nothing.
2. **The null is wrong.** `E[closedPnl] = 0` is not "random". A random trader on
   a perp DEX has *negative* expected PnL from fees and funding, so "worse than
   random" as implemented means "lost money" — which is most participants.
3. **The test is saturated.** `avg(num_trades)` is 1,373, and at that n a t-test
   rejects on any trivial nonzero mean. 1,682 of 6,911 traders clear p < 0.01, so
   significance carries no information here.

Three further problems with the inputs:

- `closedPnl` is unnormalized dollars, so the score tracks position size more
  than decision quality.
- Opening fills carry `closedPnl = "0.0"` and are counted as observations, which
  is why `avg(win_rate)` among "bad" traders is 0.201.
- `sharpe_ratio` (`core/statistics.py:231`) is `(mean/std) * sqrt(250)` computed
  on per-*fill* dollar PnL, as if each fill were a trading day. It is not a
  Sharpe ratio.

There is no multiple-testing correction across 6,911 traders, and nothing here
verifies that a trader scored bad in one period is still bad in the next.

A replacement based on execution timing was built in
[`../../research/execution_analyzer/`](../../research/execution_analyzer/).
**It also failed.** A separate test then showed that trader performance does not
persist in any tradable way at all. Consumers of this score — `../contrarian/`,
`../follower/`, `../observer/` — should be read with both results in mind.

## What it actually does

Reads unanalyzed addresses from `data/addresses.db` (read-only), fetches each
one's complete history from the `userFills` endpoint, computes summary
statistics, and writes a row to `data/analyzed_traders.db`.

Traders are skipped if they have fewer than 30 trades, an account younger than
10 days, or a balance under $500. A trader skipped for looking like a market
maker — high volume, high balance — is recorded in the `market_makers` table
instead, which is what `../market_makers/` consumes. Scored traders are
re-analyzed every 7 days.

The statistics computed per trader: mean and standard deviation of `closedPnl`,
a one-sample t-test against zero, a Monte Carlo percentile, expected value, win
rate, and average win/loss. These are combined into the 0–100 score.

## Run

```bash
cd pipeline/analyzer
python main.py --mode continuous     # run until stopped
python main.py --mode once --limit 50
```

It must be started from its own directory — the database paths in
`config/config.yaml` are relative to it.

Dependencies come from the repo-root `requirements.txt`; there is no
module-level one.

## Configuration

`config/config.yaml`. Full reference in
[`../../docs/CONFIGURATION.md`](../../docs/CONFIGURATION.md).

Concurrency is 3 at 5 req/sec, both lowered from the original 10 and 20 because
Hyperliquid returns 429s above that, with a 30s backoff on 429. Expect roughly
100–200 traders/hour.

## Dashboard

`http://localhost:5001` — score distribution, recently analyzed traders, and the
alert feed. Served automatically unless `dashboard.enabled` is false.

## Alerts

A trader scoring at or below `alert_score_threshold` (5) with p < 0.01 is
written to `logs/bad_traders_alert.log` as JSON and surfaced on the dashboard.
Given the measured behaviour above, read these as "lost money" rather than
"statistically bad".

## Export

```bash
cd pipeline/analyzer
python export_to_csv.py                       # all tables -> exports/
python export_to_csv.py --table scored_traders
python export_to_csv.py --list-tables
python export_to_csv.py --output-dir ./elsewhere
```

Output lands in the repo-root `exports/` with a timestamped filename.

## Schema

`scored_traders`, `analysis_log` and `market_makers` are documented in
[`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md#dataanalyzed_tradersdb).
