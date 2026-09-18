# Project Structure

## Main Sections

### Fetcher
Monitors all the trades being made and stores the addresses. It is useful to understand who is actually active at the moment.

```bash
# Terminal 1: Start Phase 1 (Fetcher)
cd fetcher && python3 main.py
```

### Analyzer
Retrieves the traders' account history to process an analysis of the traders 'ability' (does he makes money?). A score is assigned to each
trader based on a monte carlo simulation. [the score system needs to be checked because I am not sure is very effective]

```bash
# Terminal 2: Start Phase 2 (Analyzer)
cd analyzer && python3 main.py 
```

### Contrarin
Fetches the open positions of traders who scored worst and determines their bias. We then what to take the opposite side.

```bash
# Terminal 3: Start Phase 3 (Contrarian)
python3 contrarian/main.py
```

### Simulator
It was meant to simulate the performance of a portfolio that acts on the signal based from 'contrarian'. I later realized that the code is wrong and the simulation is not accurate.
To better simulate the performance I created strat-analyzer.ipynb 

## Add-ons

### Market-makers
It is a copy of analyzer to find market makers active. The only thing that changes from analyzer are the parameters to filter for high volume, high account equity. Market makers may move funds so to track the active ones, this module needs to be started periodically. Of course this needs new address so it must be started parallel with 'Fetcher'.

### Observer
This module was not used much so there are some issues. The idea was to retrieve the traders' data individually and judge them manually. I wanted to verify that the 'Analyzer' module was doing a good job. Haven't used it much tho.


NOTE: All the other folders dont need particular explanation.

## Findings and Observations

My thesis was that the signal would change more drastically when the price was overextended, anticipating an immediate pivot point. This was not the case and I actually recorded only a short signal for the whole duration of the test. The price ended up falling later but I am not sure it is accurate. A new test needs to be done in a while to check if something changes in the signal (or continued monitoring of course).

I monitored more closely btc, eth and sol and I found that the signal was not changing much. Perhaps following smallest asset may have a different result.

I am still convinced that one can find alpha by inverting the trades of bad market paricipants. The biggest flow of this project is the valuation method imo. I think a big change is needed there and a bit more thought.

Overall fun stuff. I will keep this for reference.

---

## Update 2026-09-18: the valuation method was measured

Your two instincts in the notes above — *"the score system needs to be checked
because I am not sure is very effective"* and *"the biggest flaw of this project
is the valuation method"* — were both right, and it turned out to be worse than
"not very effective".

**The analyzer score is a PnL-sign classifier.** All 1,723 traders at
`score <= 5` have negative total PnL; all 1,284 at `score >= 95` have positive.
Perfect separation. It is not testing anyone against random. Details in
`analyzer/README.md`.

**A replacement was built and it also failed.** `execution-analyzer/` scores
traders on execution *timing* instead of PnL: cluster fills into decisions, throw
away liquidations, maker fills, spot legs and TWAP slices, measure the
drift-demeaned and volatility-normalized forward return at 12h and 1d, and test
against a null that time-shifts prices under fixed timestamps. Run on 2,548
traders and 4.2M fills, it failed its own pre-registered gate on two counts that
matter more than the statistics:

- **No specificity.** The traders the old score calls *good* — the ones making
  money — time *worse* than the bad ones (−0.10 vs −0.04). Ranking by this metric
  to build a fade roster would preferentially pick the profitable traders.
- **No persistence.** Timing quality in one half of a trader's history does not
  predict the other half (rho = −0.076, p = 0.23), and the ordering inverts: the
  worst decile in period A comes back *least* negative in period B.

**Why fading looks hard from here.** Median holding period in the sample is 3.8
hours, against measurement horizons of 12h and 1d. The traders who score worst
are disproportionately ones trading a shorter timeframe successfully — they were
right on their own clock and closed hours before the horizon we measured. Fading
them means betting against a position that no longer exists.

**Also worth knowing: the contrarian signal was close to a constant.** Over 3,732
signals per coin, BTC was SHORT 96.6% of the time (ETH 80.6%, SOL 85.3%) while
BTC fell 12.7%. The cohort sits at ~60% long and never drops below 37%, so the
raw positioning level can essentially never produce a LONG signal. Whatever edge
that period showed is arithmetically hard to separate from `-1 x drift`. An
independent check on the stored snapshots agrees: fading the cohort's net delta
earns no significant alpha on any coin (BTC +3.4bp/day t=0.70, ETH −4.6 t=−0.64,
SOL −16.3 t=−1.37, Newey-West, net of cost).

The thesis is not dead because the code was wrong — the code was rebuilt properly
and the thesis still failed the test.

## And then the assumption underneath everything was tested too

Every module here assumes trader performance is persistent — that someone good
(or bad) in one period will still be good (or bad) in the next. That had never
been checked. `execution-analyzer/persistence.py` checks it: split each trader's
history at its own midpoint, score both halves on return on *turnover* rather
than dollars, and see whether the first half ranks the second. 1,630 traders.

**Performance does persist — but not in anything you can trade.**

It persists: net return on turnover rho = +0.066 (p = 0.008), risk-adjusted
rho = +0.132 (p = 9e-08), win rate rho = +0.421 (p = 4e-71). So the null is
rejected. Then it falls apart three ways:

- **There are no winners to follow.** Ranked on the first half, *every* decile
  has a negative median return in the second half — including the best, at
  −13.34 bp. Only 25% of traders are net-positive at all.
- **The most persistent trait is inverted.** Win rate is by far the strongest
  signal, and high win-rate traders lose *more* (median −30.26 bp vs −19.54 bp).
  Small profits taken, losses left to run. The thing you can measure most
  reliably is the thing you least want to select on.
- **What persists is the cost structure, not an edge.** Median gross −11.64 bp,
  fee drag +8.31 bp, net −21.26 bp. The top decile is roughly break-even gross
  and loses mainly to fees.

And direction — the only part a contrarian trade could actually capture — does
not persist at all: rho(first-half net ROI, second-half timing) = −0.022,
p = 0.57. The bottom decile looked significant (−0.139, p = 0.013) but it fails
robustness: a real effect would strengthen as you go further into the tail, and
this one peaks at the 10% cut and collapses by 20%.

## So where that leaves it

Three independent tests on this data — the cohort alpha check, the timing gate,
and the persistence test — all say the same thing: **trader selection does not
work here, in either direction.** Losing traders lose to costs, turnover and risk
management rather than to being reliably wrong about market direction, and there
is no counterparty trade that captures a fee drag. To collect what these traders
lose you would have to be their exchange, not the other side of their trade.

That is a real answer to the question the project was asking, even though it is
not the answer it was hoping for. Worth knowing before building a fourth scoring
method.
