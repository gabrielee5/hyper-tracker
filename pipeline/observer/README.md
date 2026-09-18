# observer

A web UI for reviewing analyzed traders one at a time and recording a judgement
on each.

Built to sanity-check the analyzer's scoring by hand — to see whether a trader
the score called bad actually looked bad.

> **Nothing downstream consumes this module's output.** The decisions it records
> in `data/approved_traders.db` were meant to feed a hand-curated portfolio that
> was never built. Grep the repo: no module outside `observer/` reads
> `approved_traders`.

## What it does

Presents traders from `data/analyzed_traders.db` sequentially, each with its
stored metrics, a cumulative PnL timeline, and live open positions fetched from
Hyperliquid. For each one you record:

- **Follow (+1)** — worth copying
- **Invert (−1)** — worth fading
- **Reject** — discard, with an optional reason

Follow and invert go to `approved_traders` with the strategy flag; rejections go
to `rejected_traders`. The queue can be filtered to the best traders (score
85–100), the worst (0–10), or all.

API responses are cached for `cache_ttl_seconds` (300) so that paging back and
forth does not re-fetch.

## Run

```bash
cd pipeline/observer
python3 main.py
```

Then open `http://localhost:5006`. It binds `127.0.0.1` by default.

This is the only module that resolves its database paths to absolute paths
relative to its own directory, so it will in fact run from any working
directory — but start it from `pipeline/observer/` for consistency with the rest.

## Caveats

It was not used much, and it shows. There is no trader search, no way to revisit
a decision from the UI, and the statistics the review screen shows are the
analyzer's — including `sharpe_ratio`, which is
[computed wrongly](../analyzer/README.md#measured-behaviour-2026-09-18).

The filters are also built around the analyzer's score, which turned out to be a
PnL-sign classifier: "best traders, score 85–100" means "made money" and "worst
traders, 0–10" means "lost money". A manual review filtered that way is
reviewing winners and losers, not skilled and unskilled traders.

## Styling

The dashboard follows
[`../../docs/DESIGN_SYSTEM.md`](../../docs/DESIGN_SYSTEM.md).
