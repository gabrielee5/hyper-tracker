# notebooks

`strat_analyzer.ipynb` — backtest of the strategy the `contrarian` module was
built to feed.

This replaced [`../simulator/`](../simulator/) as the evaluation vehicle. The
simulator's execution was wrong in ways that were never isolated, and its Sharpe
ratio is broken; a notebook over an exported CSV is inspectable line by line,
which is the only reason to trust it more.

## Run

```bash
pip install -r requirements.txt     # adds matplotlib, scikit-learn, jupyter
cd research/notebooks
jupyter notebook strat_analyzer.ipynb
```

`sample_contrarian_signals.csv` ships with the repo, so this runs on a fresh
clone with no pipeline and no database. It is 5,637 rows — BTC, ETH and SOL at
hourly resolution, 1,879 snapshots per coin from 2025-12-23 to 2026-09-18 —
sampled from the full 189,024-row signal database by taking the last snapshot in
each hour.

To run against your own data, export it and change `CSV` in the first code cell:

```bash
cd pipeline/contrarian && python export_signals_csv.py
```

Outputs are stripped from the committed notebook. They were 97.8% of the file
size, and they go stale the moment the data changes.

## What it does

1. Sizes a position in each coin proportional to the signed confidence score,
   against a $100k book split three ways.
2. Computes per-period and cumulative P&L per coin and at portfolio level, and
   plots the equity curves.
3. Regresses signed confidence against the next period's return — the direct
   test of whether the score carries information.
4. Tries a "divergence" variant: fade the cases where confidence and price move
   together, on the theory that the crowd leaning harder into a move that is
   already running marks an extreme.

## What it finds

Nothing works. On the shipped sample: total P&L −$6,864 over 5,634 periods, a
50.0% win rate, and no significant relationship between signed confidence and
the next period's return (Pearson −0.019, p = 0.16; R² = 0.0004). The divergence
variant does not rescue it.

That is consistent with everything else in `../`. Bear in mind too that the
signal being tested here was SHORT ~96% of the time on BTC, so most of what the
equity curve shows is `-1 x drift` rather than anything the confidence score
contributed — see
[`../../pipeline/contrarian/README.md`](../../pipeline/contrarian/README.md#known-problems).

The notebook's own commentary is left as it was written, including a markdown
cell that admits the divergence idea was not well specified ("It is not what I
meant but actually I dont really know what i wanted"). That is an honest record
of an exploratory session and it is more useful than a tidied-up version.

## History

There used to be two near-identical notebooks — `strat-analyzer.ipynb` and
`strat-analyzer-simulator.ipynb` — differing only in which CSV they loaded
(contrarian signals vs simulator trade exports) and one extra plot. They are
merged here; swapping the input is a one-line change in the loader cell.
