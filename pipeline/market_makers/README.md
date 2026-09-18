# market_makers

Tracks the net directional exposure of accounts that look like market makers.

## What it does

The analyzer skips traders that are too large or too active to score
meaningfully and records them in the `market_makers` table of
`data/analyzed_traders.db` instead. This module reads that table, filters to
accounts above `min_mm_balance` (default $50k), fetches their open positions
every `fetch_interval_seconds` (default 900), and computes their collective net
delta per asset.

The delta is classified against two thresholds: below
`neutral_threshold_percent` (10%) reads as NEUTRAL, above
`strong_bias_threshold_percent` (30%) as strongly directional, with BULLISH /
BEARISH in between. `weight_by_account_size` is off by default, so every
qualifying account counts equally.

Snapshots are retained 7 days, bias history 30.

## Run

```bash
cd pipeline/market_makers
python main.py
```

**Must be started from its own directory** — unlike contrarian and follower,
this module does not chdir on startup, so its `../../data/...` config paths
resolve against whatever directory you launch it from.

Dependencies come from the repo-root `requirements.txt`; there is no
module-level one.

Dashboard on `http://localhost:5003`.

## Caveats

**The roster goes stale.** Market makers move funds between wallets, so an
address that was a market maker last month may be empty now. Keeping the roster
current means running `../fetcher/` alongside this to keep discovering new
addresses, and re-running `../analyzer/` to classify them.

**"Market maker" here is a heuristic, not an identification.** It means high
volume and high balance relative to the rest of the address pool. It does not
distinguish a genuine liquidity provider from a large directional trader.

**Nothing consumes `data/mm_positions.db`.** This module is a viewer; its output
does not feed the signal modules.

## Relation to the other modules

Structurally this is a fork of [`../contrarian/`](../contrarian/), not of
`../analyzer/` — `core/position_fetcher.py` and `core/price_fetcher.py` are
byte-identical to contrarian's, and it uses the same JSON-plus-dataclasses
config style. The genuinely new code is `core/bias_analyzer.py` and the
`position_snapshots` / `bias_history` / `mm_activity` schema.
