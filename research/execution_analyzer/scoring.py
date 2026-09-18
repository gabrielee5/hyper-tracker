"""Execution-timing scoring: decision reconstruction, normalization, null tests.

Design notes worth keeping in mind while reading:

* The unit is a *decision*, not a fill. One order fills in many pieces; counting
  fills as independent observations is what inflates the current analyzer's n.

* Two price measures are computed, and the PRIMARY is the bar-grid one:

    z_grid : entry = close of the bar CONTAINING the fill, exit = close n bars later.
             Spread-free, invariant to the trader's own execution, and it is what a
             fader could actually trade given up to an hour of observation latency.
             This is the measure the nulls and the score are built on.

    z_exec : entry = the trader's own fill VWAP, exit = close n bars later.
             Measures the trader's execution as they experienced it, but it is
             contaminated by the buy-at-ask / sell-at-bid half-spread (the pilot's
             population-wide -0.05 sigma), so it needs a cohort-mean correction and
             is reported as a secondary view only.

* Drift and vol are both TRAILING (30d), never full-sample. Full-sample drift would
  leak the window's direction into the benchmark; trailing is what a live system
  could compute. Drift removal is the whole point: without it the score is
  (trader's long bias) x (market drift).

* 15m is NOT computed. 1h bars cannot resolve a 15-minute horizon, and 1m/15m
  candles only retain ~1-2 and ~35-60 days. It needs the Phase 1 rolling archive.
"""

import numpy as np

BAR_MS = 3600000                       # 1h bars
HORIZONS = {"1h": 1, "4h": 4, "12h": 12, "1d": 24}   # in bars
TRADABLE = ("12h", "1d")               # the horizons where edge can clear costs
VOL_WINDOW = 720                       # 30 days of 1h bars
CLUSTER_GAP_MS = 300000                # 5 min: fills this close collapse to one decision
COST_BPS = 10.0                        # 4.5bp taker x2 + ~1bp slippage, round trip

FLIPS = ("Long > Short", "Short > Long")


class PriceSeries:
    """1h closes for one coin, with trailing-normalized forward returns precomputed.

    zbar[h][i] is the drift-demeaned, vol-normalized forward return of a LONG
    entry at the close of bar i held for horizon h. A decision with sign s at bar
    i therefore scores s * zbar[h][i], and the time-shift null is just
    s * zbar[h][i + delta] -- which is why this is precomputed as an array.
    """

    def __init__(self, candles):
        candles = sorted(candles, key=lambda x: x["t"])
        self.t0 = candles[0]["t"]
        self.close = np.array([float(c["c"]) for c in candles])
        self.n_bars = len(self.close)
        self.zbar, self.vol, self.drift = {}, {}, {}
        for h, n in HORIZONS.items():
            self._build(h, n)

    def _build(self, h, n):
        c = self.close
        r = np.log(c[n:] / c[:-n])                  # r[i] = return of bar i -> i+n
        L = len(r)
        W = VOL_WINDOW
        cs = np.concatenate([[0.0], np.cumsum(r)])
        cs2 = np.concatenate([[0.0], np.cumsum(r * r)])
        mu = np.full(L, np.nan)
        sd = np.full(L, np.nan)
        # Trailing window is [i-W, i): strictly past data only.
        idx = np.arange(W, L)
        m = (cs[idx] - cs[idx - W]) / W
        v = (cs2[idx] - cs2[idx - W]) / W - m * m
        mu[idx] = m
        sd[idx] = np.sqrt(np.maximum(v, 0.0))
        with np.errstate(invalid="ignore", divide="ignore"):
            z = (r - mu) / sd
        z[~np.isfinite(z)] = np.nan
        self.zbar[h] = z
        self.vol[h] = sd
        self.drift[h] = mu

    def bar_of(self, t_ms):
        """Index of the bar containing t. Its close is the first close at-or-after t."""
        i = (t_ms - self.t0) // BAR_MS
        return int(i) if 0 <= i < self.n_bars else -1

    def z_grid(self, h, bar, sign):
        z = self.zbar[h]
        if bar < 0 or bar >= len(z):
            return None
        v = z[bar]
        return None if not np.isfinite(v) else sign * float(v)

    def z_exec(self, h, bar, sign, vwap):
        """Same horizon, but measured from the trader's own fill price."""
        n = HORIZONS[h]
        if bar < 0 or bar + n >= self.n_bars:
            return None
        sd, mu = self.vol[h][bar], self.drift[h][bar]
        if not (np.isfinite(sd) and np.isfinite(mu)) or sd <= 0:
            return None
        r = float(np.log(self.close[bar + n] / vwap))
        return sign * (r - float(mu)) / float(sd)


def is_perp_major(fill, majors):
    return fill.get("coin") in majors


def fill_flags(fill):
    d = str(fill.get("dir", ""))
    return {
        "is_open": d.startswith("Open") or d in FLIPS,
        "is_close": d.startswith("Close"),
        "is_spot": d in ("Buy", "Sell"),
        "is_liq": fill.get("liquidation") is not None or "iquidat" in d,
        "is_maker": fill.get("crossed") is False,
        "is_twap": fill.get("twapId") is not None,
    }


def maker_share(fills):
    if not fills:
        return 0.0
    return sum(1 for f in fills if f.get("crossed") is False) / len(fills)


def build_decisions(fills, majors, variant="open_taker"):
    """Filter fills, then collapse same-coin same-sign runs within 5 minutes.

    variant 'open_taker' : opens and flips only -- an exit is a take-profit or a
                           stop, not a directional forecast.
    variant 'all_taker'  : every signed exposure change, exits included. Computed
                           so the data decides which framing ranks better rather
                           than the argument deciding it.
    """
    keep = []
    for f in fills:
        if not is_perp_major(f, majors):
            continue
        fl = fill_flags(f)
        if fl["is_spot"] or fl["is_liq"] or fl["is_maker"] or fl["is_twap"]:
            continue
        if variant == "open_taker" and not fl["is_open"]:
            continue
        if variant == "all_taker" and not (fl["is_open"] or fl["is_close"]):
            continue
        keep.append(f)

    keep.sort(key=lambda x: x["time"])
    out, cur = [], None
    for f in keep:
        sign = 1 if f["side"] == "B" else -1
        px, sz = float(f["px"]), float(f["sz"])
        notional = px * sz
        if (cur and cur["coin"] == f["coin"] and cur["sign"] == sign
                and f["time"] - cur["t"] <= CLUSTER_GAP_MS):
            cur["notional"] += notional
            cur["pxsz"] += px * sz
            cur["sz"] += sz
            cur["t"] = f["time"]
            cur["n_fills"] += 1
        else:
            if cur:
                out.append(cur)
            cur = {"coin": f["coin"], "sign": sign, "notional": notional,
                   "pxsz": px * sz, "sz": sz, "t": f["time"], "n_fills": 1}
    if cur:
        out.append(cur)
    for d in out:
        d["vwap"] = d["pxsz"] / d["sz"]
    return out


def measure(decisions, series):
    """Attach bar index and per-horizon z to each decision. Drops unmeasurable ones."""
    out = []
    for d in decisions:
        ps = series.get(d["coin"])
        if ps is None:
            continue
        bar = ps.bar_of(d["t"])
        if bar < 0:
            continue
        zg = {h: ps.z_grid(h, bar, d["sign"]) for h in HORIZONS}
        ze = {h: ps.z_exec(h, bar, d["sign"], d["vwap"]) for h in HORIZONS}
        if all(zg[h] is None for h in TRADABLE):
            continue
        d = dict(d, bar=bar, z_grid=zg, z_exec=ze)
        out.append(d)
    return out


def mean_z(decisions, h, key="z_grid"):
    v = [d[key][h] for d in decisions if d[key][h] is not None]
    if not v:
        return None, None, 0
    a = np.array(v)
    se = a.std(ddof=1) / np.sqrt(len(a)) if len(a) > 1 else np.nan
    return float(a.mean()), float(se), len(a)


def headline(decisions, key="z_grid"):
    """Mean z averaged over the tradable horizons -- one statistic per trader, so
    the diagnostic horizons do not add to the multiple-testing burden."""
    vals, ns = [], []
    for h in TRADABLE:
        m, _, n = mean_z(decisions, h, key)
        if m is not None:
            vals.append(m)
            ns.append(n)
    if not vals:
        return None, 0
    return float(np.mean(vals)), int(min(ns))


class Pooled:
    """Decisions grouped by coin as flat arrays, so the observed statistic and every
    null draw run through exactly the same vectorized code path."""

    def __init__(self, decisions, series, weights=None):
        self.series = series
        self.by_coin = {}
        for c in series:
            idx = [i for i, d in enumerate(decisions) if d["coin"] == c]
            if not idx:
                continue
            bars = np.array([decisions[i]["bar"] for i in idx])
            signs = np.array([decisions[i]["sign"] for i in idx], dtype=float)
            w = (np.ones(len(idx)) if weights is None
                 else np.array([weights[i] for i in idx], dtype=float))
            self.by_coin[c] = (bars, signs, w)
        self.n = sum(len(v[0]) for v in self.by_coin.values())

    def mean_at(self, delta, horizons=TRADABLE, rng=None):
        """Weighted mean z per horizon, averaged across horizons. delta=0 is observed.

        A scalar delta shifts every decision together (shared offset). Passing rng
        instead draws an independent offset per decision.
        """
        vals = []
        for h in horizons:
            num = wsum = 0.0
            for c, (bars, signs, w) in self.by_coin.items():
                z = self.series[c].zbar[h]
                L = len(z)
                if rng is not None:
                    delta = rng.integers(VOL_WINDOW, max(L - VOL_WINDOW, VOL_WINDOW + 1),
                                         size=len(bars))
                j = bars + delta
                # Wrap back into the warmed-up region rather than off the end.
                j = np.where(j >= L, j - (L - VOL_WINDOW), j)
                j = np.clip(j, VOL_WINDOW, L - 1)
                v = z[j] * signs
                m = np.isfinite(v)
                num += float((v[m] * w[m]).sum())
                wsum += float(w[m].sum())
            if wsum > 0:
                vals.append(num / wsum)
        return float(np.mean(vals)) if vals else np.nan


def timeshift_null(pooled, n_draws=500, rng=None):
    """Null: keep every sign and timestamp, shift the PRICE series underneath them.

    This preserves the trader's directional bias, the return autocorrelation, and
    the clustering of decisions in time; it breaks only the timing relationship,
    which is the hypothesis under test. A sign-flipping null would instead destroy
    the directional bias and so mis-centre any trader still carrying residual
    drift exposure. One shared offset per draw also preserves cross-trader
    correlation when this is applied to a pooled sample -- the reason a cohort of
    2000 co-positioned traders is not 2000 independent observations.
    """
    if pooled.n == 0:
        return None
    rng = rng or np.random.default_rng(0)
    obs = pooled.mean_at(0)
    if not np.isfinite(obs):
        return None
    lo = VOL_WINDOW
    hi = min(len(pooled.series[c].zbar[TRADABLE[-1]]) for c in pooled.series) - VOL_WINDOW

    shared = np.array([pooled.mean_at(int(d)) for d in rng.integers(lo, hi, n_draws)])
    shared = shared[np.isfinite(shared)]
    if len(shared) < 50:
        return None

    # Independent offsets per decision. This is the OPTIMISTIC bound: it assumes
    # the decisions are independent draws, which co-positioned traders are not.
    # Reported alongside the shared-offset p so both limits are visible rather
    # than one being quietly chosen.
    indep = np.array([pooled.mean_at(0, rng=rng) for _ in range(min(n_draws, 800))])
    indep = indep[np.isfinite(indep)]

    sd = float(shared.std(ddof=1))
    out = {
        "obs": obs,
        "null_mean": float(shared.mean()),
        "null_sd": sd,
        "z_vs_null": (obs - float(shared.mean())) / sd if sd > 0 else 0.0,
        # One-sided: the hypothesis is that these traders time WORSE than the benchmark.
        "p_worse": float((shared <= obs).mean()),
        "n_draws": len(shared),
    }
    if len(indep) >= 50:
        sd_i = float(indep.std(ddof=1))
        out["p_worse_indep"] = float((indep <= obs).mean())
        out["null_sd_indep"] = sd_i
        out["z_vs_null_indep"] = ((obs - float(indep.mean())) / sd_i) if sd_i > 0 else 0.0
    return out


def bh_fdr(pvals, q=0.10):
    """Benjamini-Hochberg. Returns (q-values, rejected mask)."""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    qv = ranked * n / (np.arange(n) + 1)
    qv = np.minimum.accumulate(qv[::-1])[::-1]
    qv = np.minimum(qv, 1.0)
    out = np.empty(n)
    out[order] = qv
    return out, out < q


def shrink(z_raw, n_dec, k=50):
    return z_raw * n_dec / (n_dec + k)


def badness(z_shrunk):
    """0-100, 0 = worst, matching the existing score's convention so contrarian
    needs only a config change. Maps the shrunk z through a normal CDF."""
    from math import erf, sqrt
    cdf = 0.5 * (1 + erf(z_shrunk / sqrt(2)))
    return int(round(100 * cdf))
