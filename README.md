# hyper-tracker

Tracking Hyperliquid traders to find out whether you can make money by copying
the good ones or taking the other side of the bad ones.

**The answer, on this data, is no — in either direction.** Three independent
tests say so. That negative result is the most useful thing in this repo, so it
is written up first, below. The code that produced it is here and re-runnable.

## The thesis

Perp DEXes are full of traders who lose money. If some of them lose
*reliably* — not just on average, but persistently enough that last month
predicts next month — then their positions are a signal. Fade the ones who are
reliably wrong, follow the ones who are reliably right.

The pipeline built to test this collects addresses from the live trade feed
(`pipeline/fetcher`), pulls each trader's fill history and scores them
(`pipeline/analyzer`), then watches what the worst-scoring cohort is holding and
emits the opposite signal (`pipeline/contrarian`), with a mirror module that
follows the best-scoring cohort instead (`pipeline/follower`).

It ran for about nine months. The dataset is 114,487 addresses, 6,911 scored
traders, and 189,024 signal snapshots from 2025-12-16 to 2026-09-18.

## What it found

### 1. The original score was measuring the wrong thing

`pipeline/analyzer` claimed to identify traders performing "significantly worse
than random". It does not. It is a profit/loss sign classifier:

| group | total_pnl < 0 | total_pnl >= 0 |
|---|---|---|
| `score <= 5` | **1723** | **0** |
| `score >= 95` | **0** | **1284** |

Perfect separation in both directions, across 6,911 traders. Three reasons it
collapsed to that:

- **The Monte Carlo adds nothing.** It draws `N(0, the trader's own sigma)`, so
  the trader's percentile within those draws is a monotone function of
  `mean/(sigma/sqrt(n))` — the t-statistic computed three lines earlier. One
  test, reported twice.
- **The null is wrong.** `E[closedPnl] = 0` is not "random". A random trader on
  a perp DEX has *negative* expected PnL from fees and funding, so "worse than
  random" as implemented means "lost money", which is most participants.
- **The test is saturated.** Mean trade count is 1,373, and at that n a t-test
  rejects on any trivial nonzero mean.

Details in [`pipeline/analyzer/README.md`](pipeline/analyzer/README.md). The
module is kept, running and unchanged, as the baseline a replacement had to beat.

### 2. The replacement, scoring execution timing instead, also failed

`research/execution_analyzer` scores traders on *when* they trade rather than
how much they made: cluster fills into decisions, discard liquidations, maker
fills, spot legs and TWAP slices, measure the drift-demeaned and
volatility-normalized forward return at 12h and 1d, and test against a null that
time-shifts prices while holding signs and timestamps fixed.

Run on 2,548 traders and 4.24M fills, it failed its own pre-registered gate on
the two counts that matter most:

- **No specificity.** The traders the old score calls *good* — the ones making
  money — time **worse** than the bad ones (−0.15 vs −0.02 trader-mean). Ranking
  by this metric to build a fade roster would preferentially pick the profitable
  traders.
- **No persistence.** Timing quality in one half of a trader's history does not
  predict the other half (rho = −0.076, p = 0.23), and the decile ordering
  inverts: the worst decile in period A comes back *least* negative in period B.

Full method, the kill criteria as they were fixed before the data was seen, and
the results, in
[`research/execution_analyzer/README.md`](research/execution_analyzer/README.md).

### 3. The assumption underneath everything does not hold either

Every module here assumes trader performance is persistent. That had never been
checked. `research/execution_analyzer/persistence.py` checks it: split each
trader's history at its own midpoint, score both halves on return on *turnover*
rather than dollars, and see whether the first half ranks the second. 1,630
traders.

**Performance does persist — but not in anything you can trade.**

| metric | Spearman rho(A, B) | p |
|---|---|---|
| net return on turnover | +0.066 | 0.0075 |
| risk-adjusted (per-trade t) | +0.132 | 8.6e-08 |
| **win rate** | **+0.421** | **3.5e-71** |

The null of "no persistence" is rejected. Then it falls apart three ways:

- **There are no winners to follow.** Ranked on the first half, *every* decile
  has a negative median return in the second half — including the best, at
  −13.34 bp. Only 25% of traders are net-positive at all.
- **The most persistent trait is inverted.** Win rate is by far the strongest
  signal, and high win-rate traders lose *more* (median −30.26 bp vs −19.54 bp).
  Small profits taken, losses left to run. The thing you can measure most
  reliably is the thing you least want to select on.
- **What persists is the cost structure, not an edge.** Median gross −11.64 bp,
  fee drag +8.31 bp, net −21.26 bp. The top decile is roughly break-even gross
  and loses mainly to fees — Barber & Odean reproduced on Hyperliquid perps.

And direction, the only part a contrarian trade could actually capture, does not
persist at all: rho(first-half net ROI, second-half timing) = −0.022, p = 0.57.

### What that adds up to

**Trader selection does not work on this dataset, in either direction.** Losing
traders lose to costs, turnover and risk management rather than to being reliably
wrong about market direction, and there is no counterparty trade that captures a
fee drag. To collect what these traders lose you would have to be their exchange,
not the other side of their trade.

Two further things worth knowing before building on any of this:

- **The contrarian signal was close to a constant.** Over 3,732 signals per coin,
  BTC was SHORT 96.6% of the time (ETH 80.6%, SOL 85.3%) while BTC fell 12.7%.
  The cohort sits at ~60% long and never drops below 37%, so the raw positioning
  *level* can essentially never produce a LONG signal. Whatever edge that period
  showed is arithmetically hard to separate from `-1 x drift`. If the module is
  kept, signal on the **deviation from a trailing baseline** instead.
- **An independent check agrees.** Fading the cohort's net delta earns no
  significant alpha on any coin: BTC +3.3 bp/day (t = +0.68), ETH −5.5
  (t = −0.77), SOL −17.4 (t = −1.47), Newey-West, net of cost, over 154 days.
  Reproduce with `research/execution_analyzer/cohort_alpha_check.py`.

The thesis is not dead because the code was wrong. The code was rebuilt properly
and the thesis still failed the test.

## Install

Python 3.12. Everything talks to Hyperliquid's public read-only REST and
WebSocket endpoints — there are no API keys and no exchange credentials
anywhere in this project.

```bash
git clone <this repo> && cd hyper-tracker
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # defaults are fine to start
```

There is exactly one `requirements.txt`, at the repo root. It covers every
module.

## Run

Each module runs from its own directory and expects the one before it to have
produced data. Nothing here is fast: the fetcher needs hours to accumulate a
useful address pool, and the analyzer processes roughly 100–200 traders/hour
under Hyperliquid's rate limits.

```bash
cd pipeline/fetcher    && python main.py                    # live trades -> addresses.db
cd pipeline/analyzer   && python main.py --mode continuous  # score traders -> analyzed_traders.db
cd pipeline/contrarian && python main.py                    # fade the worst -> contrarian_signals.db
```

Optional, all reading `analyzed_traders.db` and all independent of each other:

```bash
cd pipeline/follower      && python main.py   # mirror of contrarian, follows the best
cd pipeline/market_makers && python main.py   # tracks the presumed market makers' net delta
cd pipeline/observer      && python3 main.py  # web UI to review traders by hand
```

The research side runs offline against cached data:

```bash
python research/execution_analyzer/fetch_data.py       # ~50 min, resumable, populates the cache
python research/execution_analyzer/validate.py         # the pre-registered gate
python research/execution_analyzer/persistence.py      # the split-half test (cache only, no network)
python research/execution_analyzer/cohort_alpha_check.py
python -m pytest tests/ -q                             # 24 tests, synthetic data, no network
```

`persistence.py` and `validate.py` need the fill cache, which is 242MB for 2,548
traders and is not committed. `fetch_data.py` rebuilds it.

## Layout

```
pipeline/     live collection and signal generation
  fetcher/          WebSocket trade feed -> unique addresses
  analyzer/         per-trader statistics -> a 0-100 score (see finding 1)
  contrarian/       fades the low-scoring cohort
  follower/         follows the high-scoring cohort
  market_makers/    net delta of high-balance, high-volume accounts
  observer/         manual review UI (nothing downstream consumes its output)

research/     the offline analysis that produced the answers above
  execution_analyzer/   the timing scorer, the gate, the persistence test
  notebooks/            strategy backtest on exported signals
  simulator/            paper-trading sim; superseded, and its Sharpe is wrong

services/     macOS launchd units for running the pipeline unattended
tests/        pytest suite for the execution scorer
docs/         architecture, configuration, and the design system for the dashboards
data/         every database (gitignored — nothing ships with data)
logs/         every log file (gitignored)
exports/      CSV output (gitignored)
```

### Dashboards

Every module serves one. They are independent; run as many as you like.

| port | module |
|---|---|
| 5000 | `pipeline/fetcher` |
| 5001 | `pipeline/analyzer` |
| 5002 | `pipeline/contrarian` |
| 5003 | `pipeline/market_makers` |
| 5004 | `research/simulator` (three-asset variant) |
| 5005 | `pipeline/follower` |
| 5006 | `pipeline/observer` |
| 5007 | `research/simulator` |

`pipeline/contrarian` also renders a Rich console dashboard in the terminal it
runs in.

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how the modules fit together, and the database schemas
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — every config file and what each setting does
- [`docs/CONFIDENCE_SCORE.md`](docs/CONFIDENCE_SCORE.md) — how the signal confidence is derived
- [`docs/TRACK_ROLE_GUIDE.md`](docs/TRACK_ROLE_GUIDE.md) — why maker/taker filtering matters, and why the fetcher cannot do it
- [`docs/DATA_ACCESS.md`](docs/DATA_ACCESS.md) — querying and exporting the databases
- [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md) — what is still unanswered, and what is not worth trying
- [`docs/archive/`](docs/archive/) — historical artifacts, kept for reference, not current

## A note on reading this code

This was a personal research project, and it shows in places. `pipeline/follower`
is 95% a copy of `pipeline/contrarian` with one comparison operator flipped.
`research/simulator` has a Sharpe ratio that is simply wrong. Those are labelled
where they occur rather than quietly fixed, because the point of publishing this
is the result and the method, not the craftsmanship.

The part worth reading closely is `research/execution_analyzer`: the kill
criteria were written down before the data was seen, and the module reports its
own failure against them.

## License

MIT — see [LICENSE](LICENSE).

Research and educational use. Nothing here is financial advice, and the one
conclusion it reaches with any confidence is that the strategy it set out to
build does not work.
