# contrarian

Watches what the worst-scoring traders are holding and emits the opposite
signal.

> **This module's premise did not survive testing.** Fading this cohort earns no
> significant alpha on any coin, and the signal it produces was close to a
> constant. Details in [Known problems](#known-problems). It is kept because it
> produced the dataset the analysis ran on.

## What it does

Every `update_interval_seconds` (default 1800), it:

1. reads every trader with `score <= bad_trader_score_threshold` (default 10)
   from `data/analyzed_traders.db`, read-only;
2. fetches each one's current `clearinghouseState` from Hyperliquid;
3. aggregates open positions by coin, two ways — by trader count, and weighted
   by position value in USD;
4. emits the inverse of the cohort's net positioning, with a confidence score;
5. writes one row per coin to `data/contrarian_signals.db`, plus the individual
   positions behind it.

### Signal logic

| cohort positioning | signal |
|---|---|
| >= 70% long | STRONG SHORT |
| 50–70% long | MODERATE SHORT |
| >= 70% short | STRONG LONG |
| 50–70% short | MODERATE LONG |
| otherwise | NEUTRAL |

A signal needs at least `min_traders_for_signal` (default 10) traders holding
that coin. `primary_metric` on each row records whether the count-based or the
size-weighted aggregation drove it.

Note that `moderate` is configured at `0.50`, not the `0.60` the original docs
claimed. At `0.50` the moderate band has no width on the majority side, so every
non-neutral reading becomes a signal.

### Confidence

```
imbalance         = |long_pct - 50| / 50
sample_multiplier = min(1, traders / (min_traders_for_signal * 3))
confidence        = imbalance * sample_multiplier
```

The two factors **multiply**. Earlier documentation described a weighted sum,
`(imbalance * 0.7) + (sample_factor * 0.3)`, which was never what the code did —
at 60% long with 10 traders that formula gives 0.23 where the code gives 0.067.
The derivation is in
[`../../docs/CONFIDENCE_SCORE.md`](../../docs/CONFIDENCE_SCORE.md).

## Run

```bash
python pipeline/contrarian/main.py
```

Runs from anywhere — `main.py` chdirs to its own directory on startup.

Requires `data/analyzed_traders.db` to exist and contain traders below the
threshold:

```bash
sqlite3 data/analyzed_traders.db \
  "SELECT COUNT(*) FROM scored_traders WHERE score <= 10"
```

## Dashboards

- **Terminal** — a Rich console dashboard renders in the terminal it runs in,
  refreshing every `dashboard.refresh_rate` seconds.
- **Web** — `http://localhost:5002`, with per-coin confidence history.

`dashboard.priority_coins` pins the listed coins to the top regardless of signal
strength, so the ones you care about stay visible when a long tail of alts
outranks them.

## Telegram

Optional. Signal changes on `telegram.watched_coins` are pushed to a bot. Copy
`.env.example` to `.env` and fill in:

```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

`.env` is gitignored. Set `telegram.enabled` to `false` to run without it.

## Export

```bash
cd pipeline/contrarian
python export_signals_csv.py --stats              # summary, no export
python export_signals_csv.py                      # signals -> exports/
python export_signals_csv.py --type positions     # the position snapshots
python export_signals_csv.py --coin BTC --limit 5000
python export_signals_csv.py -o my_signals.csv
```

Output lands in the repo-root `exports/`. This is how the input to
`research/notebooks/` was produced.

## Stop-loss analysis

`stop_loss_analyzer.py` is a standalone study of where the cohort's positions
would have been liquidated, given their entry prices and leverage. It reads
`data/analyzed_traders.db` and prints a report; it is not part of the signal
loop.

## Known problems

**The signal was close to a constant.** Over 3,732 signals per coin, BTC was
SHORT 96.6% of the time (ETH 80.6%, SOL 85.3%) while BTC fell 12.7%. The cohort
sits at ~60% long and never drops below 37%, so the raw positioning *level* can
essentially never produce a LONG signal. Whatever edge that period showed is
arithmetically hard to separate from `-1 x drift`.

**Fading the cohort earns nothing.** An independent check on the stored
snapshots — daily-rebalanced short of the cohort's net delta, OLS with
Newey-West errors, net of cost, 154 days — finds no significant alpha on any
coin: BTC +3.3 bp/day (t = +0.68), ETH −5.5 (t = −0.77), SOL −17.4 (t = −1.47).
Reproduce with `research/execution_analyzer/cohort_alpha_check.py`.

**The roster is selected by a broken score.** `bad_trader_score_threshold`
filters on the analyzer's score, which is a PnL-sign classifier rather than a
skill test — see [`../analyzer/README.md`](../analyzer/README.md).

**The cohort's losses are not directional.** The split-half persistence test
found that what persists about losing traders is their cost structure and risk
management, not being wrong about direction, and direction itself does not
persist at all (rho = −0.022, p = 0.57). A contrarian trade cannot capture a
counterparty's fee drag.

If the module is kept, the one change with a rationale behind it is to signal on
the **deviation from a trailing baseline** — say a 30-day percentile of cohort
positioning — rather than the absolute level, which is what makes the signal
near-constant.
