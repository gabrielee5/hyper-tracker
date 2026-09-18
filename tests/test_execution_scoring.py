"""Tests for the execution-timing scorer.

Each test here corresponds to a failure mode that was actually identified while
designing this, not to a line of code:

  * look-ahead      -- measuring the exit from a bar that contains the fill
  * benchmark drift -- a normalization that does not actually centre at zero
  * a broken null   -- the defect in the existing analyzer, whose Monte Carlo
                       draws N(0, the trader's own sigma) and so just re-encodes
                       the t-statistic it already computed
  * fake sample size-- counting each partial fill of one order as a decision
  * filter leakage  -- liquidations, maker fills, spot legs scored as decisions

Synthetic data throughout: no network, no cache.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "execution-analyzer"))
import scoring  # noqa: E402

BAR = scoring.BAR_MS
T0 = 1700000000000
N_BARS = 2000          # must exceed VOL_WINDOW + max horizon


def make_candles(n=N_BARS, seed=0):
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.004, n)
    px = 50000 * np.exp(np.cumsum(r))
    return [{"t": T0 + i * BAR, "T": T0 + (i + 1) * BAR - 1,
             "o": px[i], "c": px[i], "h": px[i], "l": px[i], "v": 1, "n": 1}
            for i in range(n)]


@pytest.fixture
def series():
    return {c: scoring.PriceSeries(make_candles(seed=i))
            for i, c in enumerate(("BTC", "ETH", "SOL"))}


def fill(t, side="B", coin="BTC", px=50000.0, sz=1.0, dir_="Open Long", **kw):
    f = {"time": t, "side": side, "coin": coin, "px": str(px), "sz": str(sz),
         "dir": dir_, "closedPnl": "0.0", "crossed": True}
    f.update(kw)
    return f


# --- normalization -----------------------------------------------------------

def test_benchmark_is_centred_and_unit_scale(series):
    """zbar must be ~N(0,1): mean 0 means drift is actually removed, sd 1 means
    horizons and coins are comparable. If the mean drifts from 0, the score
    measures (long bias x market drift) -- the artifact that made the old
    contrarian signal 96.6% short."""
    for coin, ps in series.items():
        for h, n in scoring.HORIZONS.items():
            z = ps.zbar[h][np.isfinite(ps.zbar[h])]
            assert len(z) > 1000
            # The series is sampled hourly but each z spans n bars, so successive
            # values overlap and the effective sample size is len(z)/n. Bounding
            # the mean by 3 standard errors of THAT is the honest check; a fixed
            # tolerance would just be tuned to whichever seed was tried first.
            se = z.std() / np.sqrt(len(z) / n)
            assert abs(z.mean()) < 3 * se, f"{coin} {h} mean {z.mean():.3f} vs 3se {3*se:.3f}"
            assert 0.8 < z.std() < 1.25, f"{coin} {h} sd {z.std()}"


def test_trailing_window_uses_only_past_data(series):
    """Drift/vol at bar i must be computable from bars before i, so the first
    VOL_WINDOW bars have no estimate rather than a leaked one."""
    ps = series["BTC"]
    for h in scoring.HORIZONS:
        assert not np.isfinite(ps.zbar[h][:scoring.VOL_WINDOW - 1]).any()
        assert np.isfinite(ps.zbar[h][scoring.VOL_WINDOW + 50])


def test_no_lookahead_bar_close_is_after_fill(series):
    """The bar a fill lands in must close at or after the fill: its close is the
    first observable price, never one that precedes the decision."""
    ps = series["BTC"]
    rng = np.random.default_rng(3)
    for _ in range(200):
        t = T0 + int(rng.integers(0, (N_BARS - 1) * BAR))
        b = ps.bar_of(t)
        assert ps.t0 + (b + 1) * BAR - 1 >= t


# --- decision reconstruction -------------------------------------------------

def test_partial_fills_of_one_order_collapse_to_one_decision():
    """40 fills of a single order are one decision. Counting them separately is
    what inflates n in the existing analyzer."""
    fills = [fill(T0 + i * 1000) for i in range(40)]
    dec = scoring.build_decisions(fills, scoring.__dict__.get("MAJORS", ("BTC", "ETH", "SOL")))
    assert len(dec) == 1
    assert dec[0]["n_fills"] == 40


def test_fills_beyond_cluster_gap_are_separate_decisions():
    fills = [fill(T0), fill(T0 + scoring.CLUSTER_GAP_MS + 1)]
    dec = scoring.build_decisions(fills, ("BTC", "ETH", "SOL"))
    assert len(dec) == 2


def test_direction_change_splits_decisions():
    fills = [fill(T0), fill(T0 + 1000, side="A", dir_="Open Short")]
    dec = scoring.build_decisions(fills, ("BTC", "ETH", "SOL"))
    assert len(dec) == 2
    assert [d["sign"] for d in dec] == [1, -1]


def test_vwap_is_size_weighted():
    fills = [fill(T0, px=100.0, sz=1.0), fill(T0 + 1000, px=200.0, sz=3.0)]
    dec = scoring.build_decisions(fills, ("BTC", "ETH", "SOL"))
    assert dec[0]["vwap"] == pytest.approx((100 * 1 + 200 * 3) / 4)


# --- filters -----------------------------------------------------------------

@pytest.mark.parametrize("kw,dir_", [
    ({"liquidation": {"liquidatedUser": "0x1"}}, "Close Long"),  # exchange-generated
    ({}, "Liquidated Cross"),                                    # ditto, via dir
    ({"crossed": False}, "Open Long"),                           # passive quote
    ({"twapId": 7}, "Open Long"),                                # algo slice
    ({}, "Buy"),                                                 # spot leg
])
def test_non_decisions_are_dropped(kw, dir_):
    assert scoring.build_decisions([fill(T0, dir_=dir_, **kw)], ("BTC", "ETH", "SOL")) == []


def test_non_major_coins_dropped():
    assert scoring.build_decisions([fill(T0, coin="xyz:NVDA")], ("BTC", "ETH", "SOL")) == []
    assert scoring.build_decisions([fill(T0, coin="FARTCOIN")], ("BTC", "ETH", "SOL")) == []


def test_open_taker_excludes_exits_but_all_taker_keeps_them():
    """An exit is a take-profit or a stop, not a directional forecast -- so the
    primary variant drops it while the secondary keeps it, and the data decides."""
    fills = [fill(T0, dir_="Open Long"),
             fill(T0 + 10 * 60000, side="A", dir_="Close Long")]
    assert len(scoring.build_decisions(fills, ("BTC", "ETH", "SOL"), "open_taker")) == 1
    assert len(scoring.build_decisions(fills, ("BTC", "ETH", "SOL"), "all_taker")) == 2


def test_position_flips_count_as_opens():
    fills = [fill(T0, side="A", dir_="Long > Short")]
    assert len(scoring.build_decisions(fills, ("BTC", "ETH", "SOL"), "open_taker")) == 1


# --- scoring behaviour -------------------------------------------------------

def synthetic_trader(series, kind, n=300, coin="BTC", seed=5):
    """Place decisions on the bar grid with a known relationship to the future.

    'perfect' takes the profitable side of every forward move, 'anti' the losing
    side, 'random' flips a coin.
    """
    ps = series[coin]
    rng = np.random.default_rng(seed)
    bars = rng.choice(np.arange(scoring.VOL_WINDOW + 5,
                                len(ps.zbar["1d"]) - 5), size=n, replace=False)
    dec = []
    for b in sorted(bars):
        fwd = np.nanmean([ps.zbar[h][b] for h in scoring.TRADABLE])
        if not np.isfinite(fwd):
            continue
        if kind == "perfect":
            s = 1 if fwd > 0 else -1
        elif kind == "anti":
            s = -1 if fwd > 0 else 1
        else:
            s = int(rng.choice([-1, 1]))
        dec.append({"coin": coin, "sign": s, "bar": int(b),
                    "t": ps.t0 + int(b) * BAR, "notional": 1000.0,
                    "vwap": float(ps.close[b]), "n_fills": 1,
                    "z_grid": {h: ps.z_grid(h, int(b), s) for h in scoring.HORIZONS},
                    "z_exec": {h: ps.z_exec(h, int(b), s, float(ps.close[b]))
                               for h in scoring.HORIZONS}})
    return dec


def test_synthetic_extremes_score_at_the_extremes(series):
    perfect = scoring.headline(synthetic_trader(series, "perfect"))[0]
    anti = scoring.headline(synthetic_trader(series, "anti"))[0]
    rand = scoring.headline(synthetic_trader(series, "random"))[0]
    assert perfect > 0.3, perfect
    assert anti < -0.3, anti
    assert abs(rand) < 0.2, rand
    assert anti < rand < perfect


def test_badness_maps_extremes_to_the_ends_and_noise_to_the_middle(series):
    def score(kind):
        dec = synthetic_trader(series, kind)
        r = scoring.timeshift_null(scoring.Pooled(dec, series), n_draws=300,
                                   rng=np.random.default_rng(11))
        return scoring.badness(scoring.shrink(r["z_vs_null"], len(dec)))
    assert score("anti") <= 5, "an anti-timed trader must score at the bad end"
    assert score("perfect") >= 95, "a perfectly timed trader must score at the good end"
    assert 25 <= score("random") <= 75, "a coin-flip trader must land mid-scale"


def test_null_rejects_at_about_the_nominal_rate(series):
    """The real test of the null. Coin-flip traders must produce p-values that are
    roughly uniform, so ~10% fall below 0.10. The existing analyzer's Monte Carlo
    fails exactly this: drawing N(0, the trader's own sigma) rejects far too often."""
    ps = np.array([
        scoring.timeshift_null(
            scoring.Pooled(synthetic_trader(series, "random", n=200, seed=s), series),
            n_draws=300, rng=np.random.default_rng(1000 + s))["p_worse"]
        for s in range(40)
    ])
    assert 0.0 <= ps.min() and ps.max() <= 1.0
    assert ps.mean() == pytest.approx(0.5, abs=0.18), f"p-values not centred: {ps.mean()}"
    assert (ps < 0.10).mean() < 0.30, f"over-rejecting: {(ps < 0.10).mean()}"


def test_timeshift_null_preserves_directional_bias(series):
    """A trader who is always long must not be flagged merely for being long. This
    is what a sign-flipping null gets wrong and a price-shift null gets right."""
    ps = series["BTC"]
    bars = range(scoring.VOL_WINDOW + 10, scoring.VOL_WINDOW + 310)
    dec = [{"coin": "BTC", "sign": 1, "bar": b, "t": ps.t0 + b * BAR,
            "notional": 1.0, "vwap": float(ps.close[b]), "n_fills": 1,
            "z_grid": {h: ps.z_grid(h, b, 1) for h in scoring.HORIZONS},
            "z_exec": {h: ps.z_exec(h, b, 1, float(ps.close[b])) for h in scoring.HORIZONS}}
           for b in bars]
    r = scoring.timeshift_null(scoring.Pooled(dec, series), n_draws=400,
                               rng=np.random.default_rng(7))
    assert 0.05 < r["p_worse"] < 0.95, f"perma-long flagged on bias alone: p={r['p_worse']}"


# --- statistics --------------------------------------------------------------

def test_shrinkage_pulls_small_samples_toward_zero():
    assert abs(scoring.shrink(-3.0, 10)) < abs(scoring.shrink(-3.0, 500))
    assert scoring.shrink(-3.0, 10) == pytest.approx(-3.0 * 10 / 60)
    assert scoring.shrink(-3.0, 1_000_000) == pytest.approx(-3.0, rel=1e-3)


def test_bh_fdr_is_less_permissive_than_raw_alpha():
    p = np.concatenate([np.full(5, 0.001), np.linspace(0.2, 1.0, 95)])
    qv, rej = scoring.bh_fdr(p, q=0.10)
    assert rej.sum() == 5
    assert (p < 0.05).sum() >= rej.sum()
    assert np.all(np.diff(qv[np.argsort(p)]) >= -1e-12), "q-values must be monotone"


def test_bh_fdr_rejects_nothing_under_the_global_null():
    p = np.random.default_rng(0).uniform(size=2000)
    _, rej = scoring.bh_fdr(p, q=0.10)
    assert rej.sum() <= 5, f"FDR let {rej.sum()} through on pure noise"


def test_badness_is_monotone_and_bounded():
    vals = [scoring.badness(z) for z in np.linspace(-4, 4, 50)]
    assert vals[0] == 0 and vals[-1] == 100
    assert all(b >= a for a, b in zip(vals, vals[1:]))
    assert scoring.badness(0.0) == 50


def test_fifteen_minute_horizon_is_not_offered():
    """1h bars cannot resolve 15 minutes, and 15m/1m candles retain only ~35-60
    and ~1-2 days. Offering it would invite a number nobody can compute yet."""
    assert "15m" not in scoring.HORIZONS
    assert set(scoring.TRADABLE) == {"12h", "1d"}
