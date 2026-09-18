# research

The offline analysis that answered the question the pipeline was built to ask.

The short version: **trader selection does not work on this data, in either
direction.** The long version is in [`../README.md`](../README.md#what-it-found).

## [`execution_analyzer/`](execution_analyzer/)

The rigorous work, and the part of this repo most worth reading. Three things
live here:

- **A replacement scorer** based on execution timing rather than PnL, tested
  against a gate whose kill criteria were written down before the data was seen.
  It reports its own failure against them.
- **A persistence test** (`persistence.py`) of the assumption underneath every
  module in `pipeline/`: that a trader good or bad in one period stays that way.
  Performance does persist — but only in win rate, which predicts *worse*
  profitability, and not at all in direction.
- **An independent cross-check** (`cohort_alpha_check.py`) that fading the
  contrarian cohort's net delta earns no significant alpha on any coin.

`persistence.py` and `cohort_alpha_check.py` need no network — they read a local
cache and the signals database, and reproduce their published numbers exactly.
`validate.py` needs the fill cache, which is 242MB and not committed;
`fetch_data.py` rebuilds it in about 50 minutes.

```bash
python research/execution_analyzer/persistence.py
python research/execution_analyzer/cohort_alpha_check.py
python -m pytest tests/ -q          # 24 tests, synthetic data, no network
```

## [`notebooks/`](notebooks/)

A strategy backtest over exported contrarian signals — position sizing
proportional to signed confidence, per-coin and portfolio P&L, and a regression
of signed confidence against next-period return. Ships with a sample CSV so it
runs on a fresh clone.

This replaced `simulator/` as the evaluation vehicle.

## [`simulator/`](simulator/)

Paper-trading simulator. Superseded, and its Sharpe ratio calculation is wrong.
Kept for reference, labelled in place. See
[`simulator/README.md`](simulator/README.md).

## Reading order

If you only read one thing, read
[`execution_analyzer/README.md`](execution_analyzer/README.md). It states the
method, the pre-registered gate, the result, and the four candidate mechanisms
that were tested and rejected for the one effect that did survive.
