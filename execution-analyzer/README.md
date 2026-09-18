# execution-analyzer (Phase 0)

Scores a trader on **execution timing** rather than PnL, to decide who belongs in
a fade roster. `analyzer/` is deliberately left untouched so its score survives as
the baseline to beat.

## Why

The existing score is a PnL-sign classifier, not a skill test. In
`data/analyzed_traders.db`, all 1,723 traders at `score<=5` have negative total
PnL and all 1,284 at `score>=95` have positive — perfect separation. Its
"Monte Carlo" draws `N(0, the trader's own sigma)`, so its percentile is a
monotone function of the t-statistic it already computed: one test reported
twice. At `avg(num_trades)=1373` that test rejects on any trivial nonzero mean.

And a 20-trader pilot found the old score carries no timing information at all:
PnL losers averaged −0.055σ at 4h, PnL winners −0.029σ, separation inside noise
and flipping sign by horizon.

## Method

- **Unit is a decision, not a fill.** Fills on the same coin, same sign, within
  5 minutes collapse into one decision. One order filling in 40 pieces is one
  decision; counting fills is what inflates `n`.
- **Filters.** BTC/ETH/SOL perps only; opens and flips only (an exit is a
  take-profit or a stop, not a forecast); taker only (`crossed is not False`) —
  a resting order's fill time is not its decision time, and maker fills are
  adversely selected by construction; no liquidations (exchange-generated and
  backward-looking), no TWAP slices, no spot legs.
- **Two price measures.** `z_grid` (primary): entry = close of the bar containing
  the fill, exit = close *n* bars later. Spread-free, and it is what a fader could
  actually trade given up to an hour of observation latency. `z_exec` (secondary):
  entry = the trader's own VWAP, which shows their execution but carries the
  half-spread artifact (the pilot's population-wide −0.05σ).
- **Drift and vol are trailing 30d, never full-sample.** Without drift removal the
  score is `(trader's long bias) × (market drift)` — the artifact behind a
  contrarian signal that was SHORT 96.6% of the time on BTC in a −12.7% window.
  Verified on real data: `zbar` means land at −0.006 to +0.022 against 3se ≈ 0.25.
- **Null is a price time-shift**, not a sign flip: signs and timestamps stay
  fixed and the price series slides underneath. This preserves directional bias,
  return autocorrelation, and decision clustering, breaking only timing. A
  sign-flip null would mis-centre any trader carrying residual drift exposure.
  Both bounds are reported — one shared offset per draw (conservative: the
  co-positioned cohort is one bet) and independent offsets (optimistic).
- **BH-FDR at q=0.10** across traders, with expected false discoveries shown.
- **Empirical-Bayes shrinkage** toward zero by `n/(n+50)`.

## Horizons

Scored: 1h, 4h, 12h, 1d. **Tradable gate: 12h and 1d only.** Cost is ~10bp round
trip against measured realized vol (BTC 4h 83bp, 1d 216bp), so the required edge
is 0.25σ at 15m versus 0.05σ at 1d.

**15m is not computed.** 1h bars cannot resolve it, and `candleSnapshot` retains
15m for only ~35–60 days and 1m for ~1–2 weeks. It needs the Phase 1 rolling
archive and will only ever apply to future fills.

## Files

| file | role |
|---|---|
| `hl.py` | info-endpoint client, disk cache, shared 55 req/min limiter |
| `fetch_data.py` | resumable fill/candle fetch (run in background, ~50 min) |
| `scoring.py` | decisions, normalization, nulls, FDR, shrinkage |
| `wallet_clusters.py` | collapse multi-wallet entities before counting evidence |
| `validate.py` | the Phase 0 gate: six panels plus PASS/FAIL |
| `cohort_alpha_check.py` | independent cross-check on data already on disk |
| `../tests/test_execution_scoring.py` | 24 tests, synthetic data, no network |

## Run

```bash
nohup venv/bin/python3 execution-analyzer/fetch_data.py \
  > execution-analyzer/cache/fetch.log 2>&1 &     # ~50 min, resumable
venv/bin/python3 execution-analyzer/validate.py   # the gate
venv/bin/python3 execution-analyzer/cohort_alpha_check.py
venv/bin/python3 -m pytest tests/test_execution_scoring.py -q
```

## Kill criteria (fixed before the data was seen)

Phase 1 gets built only if **all** hold:

1. pooled window-B mean `z` < 0 at **both** 12h and 1d;
2. pooled permutation p ≤ 0.10;
3. implied edge net of 10bp > 0;
4. window-A bottom decile has a negative window-B mean (persistence);
5. ≥ 300 traders scorable at `n_dec >= 100`.

## Two measurements that shaped this

**Decisions are ~2.5× fewer than usable fills.** Median is ~26 per trader, not
the ~198 usable *fills*. Detectable effect at 80% power is `2.8/sqrt(n)`, so a
typical trader supports only ~0.55σ and even `n=100` supports 0.28σ — against a
1d cost-breakeven of 0.05σ. **Per-trader scores are for ranking only; the pooled
cohort test is what establishes whether the effect exists.**

**The wallet-duplication problem is ~100× smaller than it first looks.**
`position_snapshot` has 120,728 groups of `(timestamp, coin, side, size)` shared
by 2+ addresses, but 82% have sizes rounded to ≤2 decimals (39% whole numbers) —
two unrelated traders both holding exactly 1.0 ETH is a coincidence, and taking
the transitive closure over those merges 1,569 wallets into one meaningless
cluster. Requiring a non-round size *and* ≥20 repeat co-occurrences leaves 280
credible pairs over 222 addresses in 39 clusters (32 of them simple pairs, plus
one 134-wallet vault).

---

# RESULT: the gate FAILED (run 2026-09-18)

2,548 traders fetched, 0 failures. 4.24M fills, 2.11M on BTC/ETH/SOL,
1,671 traders with at least one usable decision, 19,877 out-of-sample decisions
in the bad cohort. Full output in `cache/validate_full.log`,
machine-readable in `cache/validation_open_taker.json`.

| criterion | result | |
|---|---|---|
| pooled window-B mean z < 0 at both 12h and 1d | 12h −0.0352, 1d −0.0497 | PASS |
| pooled permutation p ≤ 0.10 | p = 0.036 | PASS |
| net edge after 10bp cost > 0 | +0.44 bp | PASS |
| **target cohort worse than control** | **target −0.0425 vs control −0.1008** | **FAIL** |
| **bottom decile in A worse in B than top decile** | **bottom −0.0060 vs top −0.0955** | **FAIL** |
| **rank persistence rho > 0** | **rho = −0.076, p = 0.23** | **FAIL** |
| ≥300 traders scorable at n_dec ≥ 100 | 241 | FAIL |

## The two findings that actually kill it

**1. The metric has no specificity.** The control cohort — traders the old score
calls *good*, i.e. the ones making money — times **worse** than the target
cohort, on every weighting: trader-mean −0.152 vs −0.019, median −0.123 vs
−0.051, decision-weighted −0.092 vs −0.025. It is not a few heavy accounts; the
five largest control traders all sit between −0.02 and −0.28. Ranking traders by
this metric to build a fade roster would preferentially select the profitable
ones.

**2. There is no persistence.** Window A does not predict window B at any sample
threshold: rho = −0.076 (n=251), −0.023 (n=124), +0.053 (n=53), none significant
and the sign wanders. The decile ordering is *inverted* — the worst decile in A
has the **least** negative window-B mean (−0.006) while the best decile in A has
one of the most negative (−0.096). Same at quintiles: worst-in-A → −0.028,
best-in-A → −0.142. Bad timing in one period predicts slightly *better* timing in
the next, which is what mean-reverting noise looks like.

Without persistence there is nothing to put in a database, and without
specificity there is no way to choose whom to fade. The remaining three PASSes do
not matter: a pooled effect you cannot attribute to identifiable traders is not
tradable, and +0.44 bp sits well inside the uncertainty of the 10 bp cost
assumption itself.

## The pooled effect is real but unexplained

The population-wide negative z survives a conservative null (p = 0.036 with one
shared price offset per draw, which treats the co-positioned cohort as a single
bet). Four candidate mechanisms were tested and none fits:

- **Long bias × bear-market drift** — no. The control cohort is *less* long-biased
  (0.518 vs 0.569, decision-weighted) yet *more* negative. Drift would push the
  other way. Trailing-drift demeaning is working: the benchmark centres at −0.006
  to +0.022σ against a 3-standard-error bound of ~0.25.
- **Market impact / adverse selection** — no. Impact decays with horizon; this
  *grows*: bad cohort −0.022 (1h) → −0.053 (1d), control −0.043 → −0.115.
- **Half-spread** — no. `z_exec` (from the trader's own VWAP) and `z_grid` (from
  the next bar close) differ by only 0.002–0.008σ.
- **Holding-period mismatch** — no. Median holding period is 3.8h against 12h/1d
  horizons, so the mismatch is real, but it does not correlate with the score:
  rho = −0.056, p = 0.27, and the buckets are non-monotonic.

Both long and short decisions are negative in both cohorts (bad: −0.012 long /
−0.090 short; control: −0.067 / −0.134), so it is direction-independent. The
mechanism is genuinely open. It is not "these traders are bad" — it applies to
everyone measured.

## Variant comparison

`all_taker` (exits included) gives a weaker effect on more decisions: −0.0216
over 35,694 decisions (p = 0.014) versus −0.0425 over 19,877 (p = 0.039). Neither
framing rescues specificity or persistence, so this does not change the verdict.

## What would have to change

Not a tuning problem. A fade roster needs a *per-trader, persistent, specific*
signal, and none of the three is present. Anything further should first explain
why profitable traders score worse than unprofitable ones on forward returns —
that is the finding with real information in it, and it points away from fading
flow and toward whatever the winners are actually capturing at sub-12h horizons.

---

# PERSISTENCE TEST (run 2026-09-18)

`persistence.py`. The assumption underneath `analyzer/`, `contrarian/`,
`follower/` and `observer/`, never tested before: does a trader's performance
predict itself? Each trader's cached history is split at its own midpoint and
scored independently in each half. Performance is **return on turnover**
(`closedPnl / (|sz| * px)` per closing fill), not dollars, so a whale and a
minnow are on the same scale. 1,630 traders qualified. Output in
`cache/persistence.log`.

## Performance does persist — weakly, and in the wrong things

| metric | Spearman rho(A, B) | p |
|---|---|---|
| net return on turnover | +0.066 | 0.0075 |
| risk-adjusted (per-trade t) | +0.132 | 8.6e-08 |
| **win rate** | **+0.421** | **3.5e-71** |

So the null of "no persistence at all" is rejected. But three things make it
untradable.

**1. Every decile loses money going forward.** Ranked on window A, *every*
decile has a negative median window-B net return, including the best:
−13.34 bp. Only 25.0% of traders are net-positive in window B at all. Selecting
the top decile of past performers still hands you a trader who loses money.

**2. The most persistent trait is anti-predictive.** Win rate is by far the
strongest signal (rho = 0.42) and it predicts *worse* profitability:

| | window-B win rate | median net ROI | % profitable |
|---|---|---|---|
| high win-rate decile | 0.652 | **−30.26 bp** | 31% |
| low win-rate decile | 0.388 | **−19.54 bp** | 30% |

Traders who win often lose more — small profits taken, losses left to run. The
most reliably measurable thing about a trader is useless for selection, and
inverted at that.

**3. What persists is cost structure, not edge.** Median gross return on
turnover is −11.64 bp, median fee drag +8.31 bp, median net −21.26 bp. Going
gross→net moves the profitable share from 33.7% to 25.0%. The *top* decile is
roughly break-even gross (−7.42 bp) and loses mainly to fees (7.48 bp) — which
is the Barber & Odean and Taiwan day-trader result reproduced on Hyperliquid
perps.

## And direction — the part a fade would actually capture — does not persist

Crossing this against the timing experiment: past PnL does not rank future
directional quality. Spearman rho(window-A net ROI, window-B timing z) =
**−0.022, p = 0.57** across 668 traders.

The bottom decile by past PnL did show a significant pooled timing z of −0.139
(p = 0.013), which would be the fade case. It does not survive scrutiny:

| cut | traders | trader-mean z | pooled p |
|---|---|---|---|
| bottom 5% | 27 | −0.112 | 0.056 |
| bottom 10% | 43 | −0.132 | 0.013 |
| bottom 20% | 109 | −0.031 | 0.061 |
| bottom 30% | 170 | −0.032 | 0.023 |

A real "worse traders are more directionally wrong" gradient would strengthen
monotonically toward the tail. This peaks at 10% and collapses by 20%. It also
halves when the 3 most extreme of 43 traders are dropped (−0.132 → −0.070). One
significant p-value at one cut point, after this many cuts, is not evidence.

## Conclusion

**Both directions are closed.**

- **Following winners** fails because there are no winners to follow: the best
  decile of past performers still has a negative median forward return.
- **Fading losers** fails because the persistent part of their loss is costs,
  turnover and risk management — not direction. You cannot capture a
  counterparty's fee drag by taking the other side of their trade. To harvest
  what these traders lose you would have to be their exchange, not their
  counterparty.

This is consistent across three independent tests on this data: the cohort alpha
check (no positive alpha on any coin), the execution-timing gate (no specificity,
no persistence), and this one (persistence exists but not in the tradable
component).

The honest reading is that trader selection does not work on this dataset, in
either direction, and further variations on scoring are not where the remaining
value is.
