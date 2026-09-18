# pipeline

The live side of the project: collect addresses, score the traders behind them,
and turn the resulting cohort's positioning into a signal.

Read [`../README.md`](../README.md) first if you have not — the conclusion is
that none of this produces a tradable edge. These modules are what generated the
data that conclusion was drawn from.

## Order

```
fetcher ──▶ analyzer ──┬──▶ contrarian
                       ├──▶ follower
                       ├──▶ market_makers
                       └──▶ observer
```

`fetcher` and `analyzer` must run in that order, and the analyzer needs the
fetcher to have collected addresses first. Everything after the analyzer is
optional and independent — run one, all, or none.

```bash
cd pipeline/fetcher    && python main.py
cd pipeline/analyzer   && python main.py --mode continuous
cd pipeline/contrarian && python main.py
```

The first two must be started **from their own directory**; so must
`market_makers` and `observer`. `contrarian` and `follower` chdir on startup and
run from anywhere.

## The modules

| module | what it does | reads | writes | port |
|---|---|---|---|---|
| [`fetcher/`](fetcher/) | WebSocket trade feed → unique addresses | Hyperliquid WS | `data/addresses.db` | 5000 |
| [`analyzer/`](analyzer/) | per-trader statistics → a 0–100 score | `addresses.db` | `data/analyzed_traders.db` | 5001 |
| [`contrarian/`](contrarian/) | inverts the low-scoring cohort's positioning | `analyzed_traders.db` | `data/contrarian_signals.db` | 5002 |
| [`follower/`](follower/) | follows the high-scoring cohort | `analyzed_traders.db` | `data/follower_signals.db` | 5005 |
| [`market_makers/`](market_makers/) | net delta of high-balance accounts | `analyzed_traders.db` | `data/mm_positions.db` | 5003 |
| [`observer/`](observer/) | manual trader review UI | `analyzed_traders.db` | `data/approved_traders.db` | 5006 |

Every read is a read-only SQLite connection. No module writes to another's
database, so they can run concurrently.

## What to know before reading the code

**`analyzer`'s score is a PnL-sign classifier**, not the test against random it
claims to be. Every module downstream selects its cohort with that score, so
"bad traders" means "traders who lost money". See
[`analyzer/README.md`](analyzer/README.md).

**`follower` is 95% a byte-identical copy of `contrarian`.** The differences are
one comparison operator and two config values, and a few things contrarian has
that follower simply lacks. See [`follower/README.md`](follower/README.md).

**`market_makers` is a fork of `contrarian`, not of `analyzer`** —
`core/position_fetcher.py` and `core/price_fetcher.py` are byte-identical
between all three.

**`observer`'s output has no consumer.** Nothing reads `approved_traders.db`.

## Configuration

Each module keeps its own config in its own format. The full reference is
[`../docs/CONFIGURATION.md`](../docs/CONFIGURATION.md); the schemas are in
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).
