# Open questions

What is still unanswered here, and — more usefully — what has been answered
already so nobody repeats it.

## Settled: do not build another scoring method

Three independent tests on this dataset agree that trader selection does not
work, in either direction:

1. **The cohort alpha check** — fading the contrarian cohort's net delta earns
   no significant alpha on any coin.
2. **The execution-timing gate** — the replacement scorer has no specificity
   (profitable traders time *worse*) and no persistence.
3. **The split-half persistence test** — performance persists, but only in win
   rate, which predicts worse profitability; direction does not persist at all.

The money in this system goes to whoever collects the fees, not to whoever picks
the direction. Median gross return on turnover is −11.64 bp and median fee drag
is +8.31 bp, so what reliably distinguishes traders is their cost structure —
and you cannot capture a counterparty's fee drag by taking the other side of
their trade.

A fourth scoring method is not where the remaining value is. The one finding
with real information in it is the one nobody has explained: **why do
profitable traders score worse than unprofitable ones on forward returns?** That
points away from fading flow and toward whatever the winners are capturing at
sub-12h horizons. Median holding period in the sample is 3.8 hours against
measurement horizons of 12h and 1d.

## Worth doing

**Signal on the deviation, not the level.** The contrarian signal was SHORT
96.6% of the time on BTC because the cohort sits at ~60% long and never drops
below 37%, so the absolute positioning level can essentially never trigger a
LONG. Signalling on the deviation from a trailing baseline — a 30-day percentile,
say — is the one change to that module with a rationale behind it. It would not
rescue the thesis, but it would make the signal informative about something
other than drift.

**A shorter measurement horizon.** The timing test could only measure 12h and 1d
because `candleSnapshot` retains 15m data for about 35–60 days and 1m for one to
two weeks, and 1h bars cannot resolve anything shorter. Against a median 3.8-hour
holding period, that mismatch is real: fading a trader at a 12h horizon means
betting against a position that closed hours earlier. Measuring it properly needs
a rolling archive of fine-grained candles built forward from now, which the
fetcher could do but does not.

**A live trade stream.** Update intervals of 1800s mean the position snapshots
miss everything that opens and closes between sweeps. A WebSocket subscription to
fills rather than periodic `clearinghouseState` polling would capture when trades
actually happen, not just what was held at sample time. This is also the
prerequisite for the shorter horizon above.

**Liquidation prices.** Each position snapshot stores `entry_price` and
`leverage_value`, so the liquidation level is computable. Clustering of
liquidation prices across a cohort is a more direct thing to trade against than
their directional bias — it says where forced flow will appear rather than
guessing who is wrong.

## Known bugs, not yet fixed

- **`pipeline/analyzer` Sharpe** (`core/statistics.py:231`) —
  `(mean/std) * sqrt(250)` on per-*fill* dollar PnL, as if each fill were a
  trading day. Stored in `scored_traders.sharpe_ratio` and surfaced in the
  observer UI.
- **`research/simulator` Sharpe** (`performance_tracker.py:65`) — a separate and
  different error: subtracts an annual 10% risk-free rate from a
  per-rebalance-period return without annualizing either.
- **`pipeline/analyzer` win rate** — opening fills carry `closedPnl = 0` and are
  counted as observations, which depresses `win_rate` across the board.

## Abandoned

**Manual trader curation.** `pipeline/observer` was built to review traders by
hand and maintain a follow/invert portfolio. The UI works; nothing consumes its
output. Given that the persistence test found no decile of past performers with
a positive median forward return, a hand-curated roster has no better prior than
an automated one.

**Machine-learned capital allocation.** The original plan was to regress
allocation weight on per-trader features — Sharpe, trade count, win rate. Two of
those three inputs are now known to be either wrong (Sharpe) or anti-predictive
(win rate: high win-rate traders lose *more*). There is no target worth
regressing onto until something is found that persists and is directional.
