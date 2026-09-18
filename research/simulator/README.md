# simulator

Paper-trades the contrarian signals against live prices, tracking a virtual
portfolio.

> **Superseded, and partly wrong.** Use `../notebooks/` for strategy evaluation.
> This module is kept for reference and because its database is the input to one
> of the notebooks — not because its results should be trusted. The specific
> defects are listed below.

## What it does

Reads signals from `data/contrarian_signals.db`, sizes positions in proportion
to signal confidence, and rebalances every `rebalance_interval_seconds` against
prices fetched from the `allMids` endpoint. Fills are charged a maker/taker fee
and a linear size-impact slippage model. State is persisted to
`data/simulator.db` and restored on restart.

Two variants, driven by two configs:

| entry point | config | allocator |
|---|---|---|
| `main.py` | `config.json` | confidence-weighted across up to 10 signals, max 40% per position |
| `main_three_asset.py` | `config_three_asset.json` | fixed one-third per asset across BTC/ETH/SOL |

See [`STRATEGY_GUIDE.md`](STRATEGY_GUIDE.md) for the comparison.

## Run

```bash
python research/simulator/main.py               # dashboard on :5007
python research/simulator/main_three_asset.py   # dashboard on :5004
```

Both chdir to their own directory on startup, so they run from anywhere. Both
require `data/contrarian_signals.db` to exist.

## What is wrong with it

**The Sharpe ratio is not a Sharpe ratio.** `performance_tracker.py:65`:

```python
sharpe = (mean_return - 0.1) / std_return
```

`mean_return` is a per-rebalance-period return — the interval is 1800 seconds —
and `0.1` is an *annual* 10% risk-free rate. Subtracting one from the other
without annualizing either is a unit mismatch of several orders of magnitude,
and it makes the reported Sharpe hugely negative regardless of performance.
Nothing else in the module corrects for it.

**The broader simulation was not trusted by its author.** From the project
notes: *"I later realized that the code is wrong and the simulation is not
accurate."* And from the git history, when it was taken out of service: *"it was
working wrong at the beginning but now it went completely loco."* The specific
conceptual error was never isolated — the module was replaced rather than
debugged.

**Its input is a near-constant signal.** Even if the execution were correct, it
is paper-trading a contrarian signal that was SHORT 96.6% of the time on BTC
over 275 days. A backtest of that is mostly a backtest of `-1 x drift`. See
[`../../pipeline/contrarian/README.md`](../../pipeline/contrarian/README.md#known-problems).

**The duplication is substantial.** `simulator.py` and
`simulator_three_asset.py` are 88% identical, `main.py` and
`main_three_asset.py` 85%. The position sizer and portfolio manager genuinely
diverge; the rest is copy-paste.

## What replaced it

[`../notebooks/`](../notebooks/) evaluates the same strategy on exported signal
CSVs, which is easier to inspect and to correct. The rigorous work is in
[`../execution_analyzer/`](../execution_analyzer/), which tests the trader
selection underneath the strategy rather than the strategy itself — and finds it
does not work.

## Export

```bash
cd research/simulator
python export_to_csv.py                        # all tables -> exports/simulator/
python export_to_csv.py --db ../../data/simulator.db
python export_to_csv.py --table trades
python export_to_csv.py --summary              # portfolio/trade/performance reports only
```

## Configuration

`config.json` / `config_three_asset.json`, referenced in
[`../../docs/CONFIGURATION.md`](../../docs/CONFIGURATION.md).
