# follower

The mirror of [`../contrarian/`](../contrarian/): reads the *best*-scoring
traders and passes their positioning through rather than inverting it.

> **This module is 95% a byte-identical copy of `contrarian/`.** That is worth
> knowing before you read it, because the parts that were not updated are the
> parts that will mislead you. See [What actually differs](#what-actually-differs).

## What it does

Every `update_interval_seconds`, reads every trader with
`score >= good_trader_score_threshold` (default 90) from
`data/analyzed_traders.db`, fetches their open positions, aggregates by coin,
and writes the cohort's direction — uninverted — to
`data/follower_signals.db`.

Signal thresholds, confidence calculation and the dual count/size-weighted
aggregation are all identical to contrarian's, documented in
[`../contrarian/README.md`](../contrarian/README.md) and
[`../../docs/CONFIDENCE_SCORE.md`](../../docs/CONFIDENCE_SCORE.md).

## Run

```bash
python pipeline/follower/main.py
```

Runs from anywhere — `main.py` chdirs to its own directory. Web dashboard on
`http://localhost:5005`.

## What actually differs

Of 3,809 lines of Python, 189 are unique to this module. `core/aggregator.py`
and `core/position_fetcher.py` are byte-identical to contrarian's.

The real differences are three:

1. **The comparison operator.** `core/database.py:75` selects
   `WHERE score >= ? ORDER BY score DESC` where contrarian has
   `WHERE score <= ? ORDER BY score ASC`.
2. **The signal mapping.** A long-leaning cohort produces LONG here and SHORT in
   contrarian.
3. **Two config values.** Threshold 90 instead of 10, port 5005 instead of 5002.

And three things contrarian has that this does not:

- **No `core/price_fetcher.py`**, so `follower_signals` has no `current_price`
  column. Signals cannot be joined to the price at the time they were emitted
  without going back to the API.
- **No `/api/confidence-history/<coin>` route** on the web dashboard.
- **No Telegram integration.**

## Status

Not seriously used. The persistence test found there are no winners to follow:
ranked on the first half of their history, *every* decile of traders has a
negative median return in the second half — including the best, at −13.34 bp —
and only 25% of traders are net-positive at all. Selecting the top decile of
past performers still hands you a trader who loses money.

See the [results summary](../../README.md#what-it-found) and
[`../../research/execution_analyzer/README.md`](../../research/execution_analyzer/README.md).

The roster is also selected by the analyzer's score, which is a PnL-sign
classifier — `score >= 90` means "made money", not "skilled". See
[`../analyzer/README.md`](../analyzer/README.md).
