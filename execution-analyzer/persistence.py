"""Does trader performance persist at all?

This is the assumption underneath analyzer/, contrarian/, follower/ and
observer/, and it has never been tested anywhere in this project. Everything
downstream assumes that a trader who was good (or bad) in one period will still
be good (or bad) in the next. If that is false, selecting traders is noise no
matter how they are scored or which direction they are traded.

Method: split each trader's cached fill history at its own midpoint, measure
risk-adjusted performance in each half independently, and ask whether the first
half ranks the second.

Performance is return on turnover, not dollars: for each closing fill,
r = closedPnl / (|sz| * px), so a whale and a minnow are on the same scale. The
old analyzer score failed partly by using unnormalized dollar PnL, which tracks
position size more than skill. Fees are charged from the fills' own `fee` field,
which covers both legs, and gross and net are reported separately -- the
literature on retail traders says they lose to costs rather than to direction, so
the distinction is the whole question.

No new network access: reads execution-analyzer/cache, populated by fetch_data.py.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent))
import hl
import scoring
import validate
import wallet_clusters

MIN_TRADES = 20          # closing fills per window
MM_MAKER_SHARE = 0.60


def window_stats(fills):
    """Performance of one window of fills. Returns None if too few closing trades."""
    rs, notional_closed, fees, gross = [], 0.0, 0.0, 0.0
    turnover = 0.0
    for f in fills:
        px, sz = float(f["px"]), abs(float(f["sz"]))
        turnover += px * sz
        try:
            fees += float(f.get("fee") or 0.0)
        except (TypeError, ValueError):
            pass
        cp = f.get("closedPnl")
        if cp is None:
            continue
        try:
            cp = float(cp)
        except (TypeError, ValueError):
            continue
        if cp == 0.0:
            continue          # opening fills carry closedPnl "0.0"; they are not trades
        n = px * sz
        if n <= 0:
            continue
        rs.append(cp / n)
        notional_closed += n
        gross += cp

    if len(rs) < MIN_TRADES:
        return None
    a = np.array(rs)
    sd = a.std(ddof=1)
    return {
        "n_trades": len(a),
        "roi_gross_bps": gross / notional_closed * 1e4,
        "roi_net_bps": (gross - fees) / notional_closed * 1e4,
        "fee_drag_bps": fees / notional_closed * 1e4,
        # t-like: mean per-trade return in units of its own standard error
        "tstat": float(a.mean() / (sd / np.sqrt(len(a)))) if sd > 0 else 0.0,
        "win_rate": float((a > 0).mean()),
        "turnover": turnover,
    }


def build(old_scores, clusters, exclude_mm=True):
    rows = []
    dropped = Counter()
    for p in sorted((Path(__file__).parent / "cache" / "fills").glob("*.json.gz")):
        addr = p.name.replace(".json.gz", "")
        fills = hl.load_fills(addr)
        if not fills:
            dropped["empty"] += 1
            continue
        if exclude_mm and scoring.maker_share(fills) > MM_MAKER_SHARE:
            dropped["mm_like"] += 1
            continue
        fills = sorted(fills, key=lambda x: x["time"])
        ts = [f["time"] for f in fills]
        span_days = (ts[-1] - ts[0]) / 86400000
        if span_days < 30:
            dropped["span<30d"] += 1
            continue
        mid = (ts[0] + ts[-1]) / 2
        A = window_stats([f for f in fills if f["time"] < mid])
        B = window_stats([f for f in fills if f["time"] >= mid])
        if A is None or B is None:
            dropped["too_few_trades"] += 1
            continue
        rows.append({"address": addr, "A": A, "B": B, "span_days": span_days,
                     "old_score": old_scores.get(addr),
                     "cluster": clusters.get(addr, addr)})
    return rows, dropped


def decile_table(rows, metric):
    a = np.array([r["A"][metric] for r in rows])
    b = np.array([r["B"][metric] for r in rows])
    order = np.argsort(a)
    print(f"\n  {'decile(A)':>9}{'n':>5}{'mean A':>12}{'mean B':>12}{'median B':>12}"
          f"{'% B > 0':>10}")
    out = []
    for d in range(10):
        idx = order[d * len(rows) // 10:(d + 1) * len(rows) // 10]
        if len(idx) == 0:
            continue
        out.append(b[idx].mean())
        print(f"  {d+1:>7}{len(idx):>7}{a[idx].mean():>12.2f}{b[idx].mean():>12.2f}"
              f"{np.median(b[idx]):>12.2f}{100*(b[idx]>0).mean():>10.1f}")
    return out, a, b


def report(rows, metric, label, unit):
    print("\n" + "=" * 78)
    print(f"{label}   (metric: {metric}, {unit})")
    print("=" * 78)
    dec, a, b = decile_table(rows, metric)
    rho, p = stats.spearmanr(a, b)
    print(f"\n  Spearman rho(A, B) = {rho:+.4f}   p = {p:.4g}   n = {len(rows)}")
    print(f"  cross-sectional window-B mean {b.mean():+.2f}  median {np.median(b):+.2f}"
          f"  ({100*(b>0).mean():.1f}% positive)")
    spread = dec[-1] - dec[0]
    print(f"  top decile minus bottom decile, in window B: {spread:+.2f} {unit}")
    print("  (this is the number a selection strategy would actually harvest; it has")
    print("   to beat ~10 bp of round-trip cost to be worth trading)")
    return {"rho": float(rho), "p": float(p), "spread": float(spread),
            "n": len(rows), "b_mean": float(b.mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-mm", action="store_true", help="do not exclude MM-like accounts")
    args = ap.parse_args()

    old = validate.load_old_scores()
    try:
        clusters = wallet_clusters.build()
    except Exception:
        clusters = {}

    print("=" * 78)
    print("PERSISTENCE TEST -- does trader performance predict itself?")
    print("=" * 78)
    print(f"  split           each trader's own history midpoint")
    print(f"  min trades      {MIN_TRADES} closing fills per window")
    print(f"  MM-like         {'kept' if args.keep_mm else 'excluded'} (>{MM_MAKER_SHARE:.0%} passive)")

    rows, dropped = build(old, clusters, exclude_mm=not args.keep_mm)
    print(f"\n  traders usable: {len(rows)}")
    for k, v in dropped.most_common():
        print(f"    dropped, {k:<16} {v}")

    print(f"\n  SURVIVORSHIP NOTE: traders with too few trades in window B are dropped,")
    print(f"  which includes anyone who blew up or quit mid-history. This sample is")
    print(f"  conditioned on still being active, so it is biased TOWARD persistence.")

    res = {}
    res["roi_net"] = report(rows, "roi_net_bps",
                            "1. RETURN ON TURNOVER, NET OF FEES", "bp")
    res["roi_gross"] = report(rows, "roi_gross_bps",
                              "2. RETURN ON TURNOVER, GROSS", "bp")
    res["tstat"] = report(rows, "tstat",
                          "3. RISK-ADJUSTED (per-trade t-statistic)", "t")
    res["win_rate"] = report(rows, "win_rate", "4. WIN RATE", "frac")

    # How much of gross performance is eaten by costs
    fd = np.array([r["B"]["fee_drag_bps"] for r in rows])
    gr = np.array([r["B"]["roi_gross_bps"] for r in rows])
    nt = np.array([r["B"]["roi_net_bps"] for r in rows])
    print("\n" + "=" * 78)
    print("5. WHERE THE MONEY GOES (window B)")
    print("=" * 78)
    print(f"  median gross return on turnover {np.median(gr):+7.2f} bp")
    print(f"  median fee drag                 {np.median(fd):+7.2f} bp")
    print(f"  median net return on turnover   {np.median(nt):+7.2f} bp")
    print(f"  traders gross-positive {100*(gr>0).mean():.1f}%  ->  net-positive {100*(nt>0).mean():.1f}%")

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    ok = []
    for k, lab in (("roi_net", "net return on turnover"), ("tstat", "risk-adjusted")):
        r = res[k]
        sig = r["p"] < 0.05 and r["rho"] > 0
        ok.append(sig)
        print(f"  [{'PASS' if sig else 'FAIL'}]  {lab:<26} rho={r['rho']:+.4f} "
              f"p={r['p']:.4g}  top-bottom spread {r['spread']:+.2f}")
    if any(ok):
        print("\n  Performance carries some signal across periods. The size of the")
        print("  top-minus-bottom spread decides whether it is tradable after costs.")
    else:
        print("\n  *** No detectable persistence. Past performance does not rank future")
        print("  performance, in either direction. Trader selection -- fading losers OR")
        print("  following winners -- has no foundation on this data. ***")


if __name__ == "__main__":
    main()
