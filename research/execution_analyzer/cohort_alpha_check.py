"""Independent cross-check, using only data already on disk.

The per-trade horizon study is one estimator of the thesis. This is a blunter and
completely separate one: take the 275 days of position_snapshot already collected,
form a daily-rebalanced portfolio that is SHORT the bad cohort's net delta, and
regress its return on the coin's own return:

    r_strat(t) = alpha + beta * r_coin(t) + e(t)

beta will come out near -1 by construction, because the cohort was net long ~60%
of the time on every single observation. The entire thesis is the claim that
alpha > 0 and survives cost. If alpha is indistinguishable from zero here, then
the apparent historical edge was -1 x market drift in a window where BTC fell
12.7%, and no amount of finer horizon analysis rescues it.

Newey-West standard errors, because daily strategy returns built from an
overlapping ~2h snapshot cadence are autocorrelated.
"""

import sqlite3
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SIGNALS_DB = ROOT / "data" / "contrarian_signals.db"
COINS = ("BTC", "ETH", "SOL")
COST_BPS = 10.0


def load(coin):
    con = sqlite3.connect(f"file:{SIGNALS_DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT timestamp, current_price, long_usd_value, short_usd_value, "
        "       long_percentage, bad_traders_total "
        "FROM contrarian_signals WHERE coin = ? AND current_price IS NOT NULL "
        "ORDER BY timestamp", (coin,)
    ).fetchall()
    con.close()
    return rows


def to_daily(rows):
    """Last observation of each UTC day -> (day, price, net_bias_fraction)."""
    per_day = {}
    for ts, px, lusd, susd, lpct, n in rows:
        day = str(ts)[:10]
        tot = (lusd or 0) + (susd or 0)
        if tot <= 0:
            # fall back to the count-based imbalance when USD values are missing
            bias = (lpct - 50.0) / 50.0 if lpct is not None else None
        else:
            bias = ((lusd or 0) - (susd or 0)) / tot
        if bias is None or px is None:
            continue
        per_day[day] = (float(px), float(bias))
    days = sorted(per_day)
    return days, np.array([per_day[d][0] for d in days]), np.array([per_day[d][1] for d in days])


def newey_west(X, y, lags=5):
    """OLS with HAC (Bartlett) standard errors."""
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta
    n, k = X.shape
    S = (X * resid[:, None]).T @ (X * resid[:, None])
    for L in range(1, lags + 1):
        w = 1.0 - L / (lags + 1.0)
        u = (X[L:] * resid[L:, None])
        v = (X[:-L] * resid[:-L, None])
        G = u.T @ v
        S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv * n / max(n - k, 1)
    se = np.sqrt(np.diag(V))
    return beta, se


def main():
    print("=" * 78)
    print("COHORT ALPHA CROSS-CHECK  (fade the bad cohort's net delta, daily rebalance)")
    print("=" * 78)
    print(f"cost charged per rebalance: {COST_BPS} bp\n")

    for coin in COINS:
        rows = load(coin)
        days, px, bias = to_daily(rows)
        if len(days) < 60:
            print(f"{coin}: only {len(days)} daily observations, skipping")
            continue

        r_coin = np.diff(np.log(px))
        # Fade yesterday's observed bias; turnover charged on position change.
        pos = -bias[:-1]
        turnover = np.abs(np.diff(np.concatenate([[0.0], pos])))
        r_gross = pos * r_coin
        r_net = r_gross - turnover * COST_BPS / 1e4

        X = np.column_stack([np.ones(len(r_coin)), r_coin])
        for lab, y in (("gross", r_gross), ("net of cost", r_net)):
            beta, se = newey_west(X, y, lags=5)
            a, b = beta
            t_a = a / se[0] if se[0] > 0 else 0.0
            ann = a * 365
            sharpe = (y.mean() / y.std() * np.sqrt(365)) if y.std() > 0 else 0.0
            print(f"{coin:>4} {lab:<12} alpha {a*1e4:+7.2f} bp/day  (t = {t_a:+5.2f}, NW)"
                  f"   beta {b:+6.2f}   ann alpha {ann*100:+6.1f}%   Sharpe {sharpe:+5.2f}")

        drift = r_coin.mean()
        print(f"{coin:>4} {'context':<12} coin drift {drift*1e4:+7.2f} bp/day   "
              f"mean cohort long bias {bias.mean():+.3f}   "
              f"days {len(days)}   price {px[0]:.2f} -> {px[-1]:.2f}")
        print()

    print("Read this as: a negative beta confirms the fade is a structural short. The")
    print("thesis lives or dies on alpha, and alpha must be positive NET of cost, with")
    print("a t-stat that means something on one non-repeatable bear-market path.")
    print()
    print("IMPORTANT SCOPE LIMIT: this tests the EXISTING roster (selected by the old")
    print("PnL score) fed through the EXISTING positioning signal. Both are independently")
    print("broken -- the score is a PnL-sign classifier and the signal was 96.6% short.")
    print("So a null result here rejects the current implementation, NOT the timing")
    print("thesis itself. validate.py is the test of the replacement. What this does")
    print("establish is that there is no banked edge to protect: nothing is lost by")
    print("rebuilding the selection rule from scratch.")


if __name__ == "__main__":
    main()
