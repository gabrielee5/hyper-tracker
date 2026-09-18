"""Phase 0 validation gate.

Answers one question before any of the pipeline gets built: is a trader's
execution timing on BTC/ETH/SOL bad in a way that (a) persists out of sample and
(b) is large enough to clear ~10bp of round-trip cost?

Kill criteria are fixed in KILL_* below and evaluated at the end. If this fails,
nothing downstream gets written -- that is the point of running it first.

Usage:  venv/bin/python3 execution-analyzer/validate.py [--variant open_taker]
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent))
import hl
import scoring
import wallet_clusters

ROOT = Path(__file__).resolve().parents[2]
SCORED_DB = ROOT / "data" / "analyzed_traders.db"

MIN_DEC_WINDOW = 25          # per window, for the persistence panel
MIN_DEC_SCORE = 100          # the production gate from the plan
MIN_SPAN_DAYS = 60           # a midpoint split is meaningless on a 3-day history
MM_MAKER_SHARE = 0.60        # above this the account is quoting, not deciding

# --- kill criteria -----------------------------------------------------------
KILL_POOLED_P = 0.10         # pooled window-B permutation p must beat this
KILL_MIN_SCORABLE = 300      # traders surviving filters with >= MIN_DEC_SCORE


def load_old_scores():
    con = sqlite3.connect(f"file:{SCORED_DB}?mode=ro", uri=True)
    rows = dict(con.execute("SELECT address, score FROM scored_traders").fetchall())
    con.close()
    return rows


def hsep(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def build_traders(series, variant, old_scores, clusters):
    """One record per cached address: decisions, midpoint split, contamination flags."""
    files = sorted((Path(__file__).parent / "cache" / "fills").glob("*.json.gz"))
    out, audit = [], Counter()
    for f in files:
        addr = f.name.replace(".json.gz", "")
        fills = hl.load_fills(addr)
        audit["cached"] += 1
        if not fills:
            audit["empty"] += 1
            continue

        mk = scoring.maker_share(fills)
        flags = [scoring.fill_flags(x) for x in fills]
        audit["fills_total"] += len(fills)
        audit["fills_maker"] += sum(1 for x in flags if x["is_maker"])
        audit["fills_liq"] += sum(1 for x in flags if x["is_liq"])
        audit["fills_spot"] += sum(1 for x in flags if x["is_spot"])
        audit["fills_twap"] += sum(1 for x in flags if x["is_twap"])
        audit["fills_major"] += sum(1 for x in fills if x.get("coin") in hl.MAJORS)

        dec = scoring.measure(scoring.build_decisions(fills, hl.MAJORS, variant), series)
        if not dec:
            audit["no_decisions"] += 1
            continue
        ts = [d["t"] for d in dec]
        span = (max(ts) - min(ts)) / 86400000

        mid = (min(ts) + max(ts)) / 2
        A = [d for d in dec if d["t"] < mid]
        B = [d for d in dec if d["t"] >= mid]
        hA, nA = scoring.headline(A)
        hB, nB = scoring.headline(B)
        hAll, nAll = scoring.headline(dec)

        out.append({
            "address": addr,
            "old_score": old_scores.get(addr),
            "maker_share": mk,
            "is_mm_like": mk > MM_MAKER_SHARE,
            "span_days": span,
            "n_fills": len(fills),
            "n_dec": len(dec),
            "n_A": len(A), "n_B": len(B),
            "z_A": hA, "z_B": hB, "z_all": hAll,
            "long_bias": float(np.mean([d["sign"] > 0 for d in dec])),
            "cluster": clusters.get(addr, addr),
            "dec": dec, "A": A, "B": B,
        })
    return out, audit


def panel_contamination(traders, audit):
    hsep("PANEL 0 - contamination audit (what the filters remove)")
    ft = max(audit["fills_total"], 1)
    print(f"  addresses cached                 {audit['cached']}")
    print(f"  fills seen                       {audit['fills_total']}")
    for k, lab in (("fills_major", "on BTC/ETH/SOL"), ("fills_maker", "passive (crossed=False)"),
                   ("fills_liq", "liquidation-flagged"), ("fills_spot", "spot legs (dir Buy/Sell)"),
                   ("fills_twap", "TWAP")):
        print(f"    {lab:<32} {audit[k]:>8}  ({100*audit[k]/ft:5.1f}%)")

    mk = np.array([t["maker_share"] for t in traders])
    print(f"\n  maker share per trader: median {np.median(mk)*100:.1f}%  "
          f"mean {mk.mean()*100:.1f}%")
    print(f"  MM-like (>{MM_MAKER_SHARE*100:.0f}% passive), excluded: "
          f"{sum(t['is_mm_like'] for t in traders)}/{len(traders)}")
    nd = np.array([t["n_dec"] for t in traders])
    print(f"  decisions per trader: median {np.median(nd):.0f}  "
          f"p25 {np.percentile(nd,25):.0f}  p75 {np.percentile(nd,75):.0f}  max {nd.max()}")
    for thr in (25, 50, 100, 200):
        print(f"    with >= {thr:>3} decisions: {int((nd>=thr).sum())}/{len(traders)}")
    print("\n  NOTE: decisions are ~2.5x fewer than usable fills -- clustering collapses")
    print("  multi-fill orders. Power scales with decisions, not fills.")


def cohort(traders, bad_only=True):
    sel = [t for t in traders if not t["is_mm_like"] and t["span_days"] >= MIN_SPAN_DAYS]
    if bad_only:
        sel = [t for t in sel if t["old_score"] is not None and t["old_score"] <= 5]
    return sel


def pooled_test(traders, series, key, label, n_draws=3000, weight_clusters=True):
    """Pool every decision in `key` across traders and test against the time-shift null."""
    decs, wts = [], []
    csize = Counter(t["cluster"] for t in traders)
    for t in traders:
        w = 1.0 / csize[t["cluster"]] if weight_clusters else 1.0
        for d in t[key]:
            decs.append(d)
            wts.append(w)
    if not decs:
        print(f"  {label}: no decisions")
        return None
    p = scoring.Pooled(decs, series, wts)
    res = scoring.timeshift_null(p, n_draws=n_draws)
    if not res:
        print(f"  {label}: null failed")
        return None
    per_h = {h: p.mean_at(0, [h]) for h in scoring.TRADABLE}
    res["per_horizon"] = per_h
    res["n_dec"] = p.n
    res["n_traders"] = len(traders)
    print(f"  {label}")
    print(f"    traders {len(traders):>5} | decisions {p.n:>7}")
    print(f"    mean z (12h,1d avg) {res['obs']:+.4f}   null {res['null_mean']:+.4f} "
          f"+/- {res['null_sd']:.4f}")
    print(f"    shared-offset null (cohort = one bet, CONSERVATIVE): "
          f"z {res['z_vs_null']:+.2f}  p {res['p_worse']:.4f}")
    if "p_worse_indep" in res:
        print(f"    independent-offset null (decisions independent, OPTIMISTIC): "
              f"z {res['z_vs_null_indep']:+.2f}  p {res['p_worse_indep']:.4f}")
    print("    per horizon: " + "  ".join(f"{h} {per_h[h]:+.4f}" for h in scoring.TRADABLE))
    return res


def vol_bps(series, h="1d"):
    return float(np.nanmean([np.nanmean(series[c].vol[h]) for c in series])) * 1e4


def panel_pooled(traders, series):
    hsep("PANEL 1 - pooled cohort test (PRIMARY RESULT)")
    print("  Null: prices time-shifted under fixed signs/timestamps, one shared offset")
    print("  per draw -- preserves directional bias, return autocorrelation, and the")
    print("  cross-trader correlation of co-positioned traders.\n")
    bad = cohort(traders, bad_only=True)
    res_B = pooled_test(bad, series, "B", "bad cohort (old score<=5), WINDOW B (out of sample)")
    print()
    pooled_test(bad, series, "A", "bad cohort, window A (in sample, for reference)")
    print()
    ctrl = [t for t in cohort(traders, bad_only=False)
            if t["old_score"] is not None and t["old_score"] >= 50]
    res_ctrl = pooled_test(ctrl, series, "B", "control (old score>=50), window B")
    if res_B and res_ctrl:
        print(f"\n  SPECIFICITY: target {res_B['obs']:+.4f} vs control {res_ctrl['obs']:+.4f}")
        print("  The target cohort must be WORSE than the control, or the metric cannot")
        print("  select whom to fade -- ranking by it would pick the profitable traders.")
        res_B["control_obs"] = res_ctrl["obs"]

    if res_B:
        sig = vol_bps(series, "1d")
        edge = -res_B["obs"] * sig
        hsep("PANEL 1b - cost arithmetic")
        print(f"  mean 1d realized vol across coins   {sig:.0f} bp")
        print(f"  pooled window-B mean z              {res_B['obs']:+.4f} sigma")
        print(f"  implied gross edge per fade         {edge:+.2f} bp")
        print(f"  round-trip cost                     {scoring.COST_BPS:.1f} bp")
        print(f"  NET                                 {edge - scoring.COST_BPS:+.2f} bp")
        res_B["net_bps"] = edge - scoring.COST_BPS
    return res_B


def panel_persistence(traders, series):
    hsep("PANEL 2 - persistence (does window A predict window B?)")
    sel = [t for t in cohort(traders, bad_only=False)
           if t["n_A"] >= MIN_DEC_WINDOW and t["n_B"] >= MIN_DEC_WINDOW
           and t["z_A"] is not None and t["z_B"] is not None]
    if len(sel) < 30:
        print(f"  only {len(sel)} traders have >= {MIN_DEC_WINDOW} decisions in both windows")
        return None
    a = np.array([t["z_A"] for t in sel])
    b = np.array([t["z_B"] for t in sel])
    rho, p = stats.spearmanr(a, b)
    print(f"  traders with both windows >= {MIN_DEC_WINDOW} decisions: {len(sel)}")
    print(f"  Spearman rho(z_A, z_B) = {rho:+.4f}   p = {p:.4f}")
    print(f"  Pearson  r             = {np.corrcoef(a,b)[0,1]:+.4f}")

    order = np.argsort(a)
    print(f"\n  {'decile(A)':>10}{'n':>5}{'mean z_A':>11}{'mean z_B':>11}{'median z_B':>12}")
    dec_means = []
    for d in range(10):
        idx = order[d*len(sel)//10:(d+1)*len(sel)//10]
        if len(idx) == 0:
            continue
        dec_means.append(b[idx].mean())
        print(f"  {d+1:>8}{len(idx):>7}{a[idx].mean():>11.4f}"
              f"{b[idx].mean():>11.4f}{np.median(b[idx]):>12.4f}")
    bottom = dec_means[0] if dec_means else None
    top = dec_means[-1] if dec_means else None
    sep = (top - bottom) if (bottom is not None and top is not None) else None
    print(f"\n  bottom decile in A -> mean z_B {bottom:+.4f}")
    print(f"  top    decile in A -> mean z_B {top:+.4f}")
    print(f"  separation (top - bottom) = {sep:+.4f}")
    print("  The thesis needs SEPARATION, not just a negative bottom decile: in a")
    print("  population that is negative everywhere, 'bottom decile is negative' is")
    print("  satisfied by noise. Selection only works if bad-in-A stays worse in B.")
    return {"rho": float(rho), "p": float(p), "bottom_decile_zB": bottom,
            "top_decile_zB": top, "separation": sep, "n": len(sel)}


def panel_baseline(traders):
    hsep("PANEL 3 - baseline: does the OLD PnL score predict timing at all?")
    sel = [t for t in cohort(traders, bad_only=False)
           if t["old_score"] is not None and t["z_all"] is not None
           and t["n_dec"] >= MIN_DEC_WINDOW]
    if len(sel) < 30:
        print("  insufficient sample")
        return None
    s = np.array([t["old_score"] for t in sel], dtype=float)
    z = np.array([t["z_all"] for t in sel])
    rho, p = stats.spearmanr(s, z)
    print(f"  traders {len(sel)}")
    print(f"  Spearman rho(old_score, timing z) = {rho:+.4f}  p = {p:.4f}")
    print("  (if ~0, the existing score carries no timing information -- the premise")
    print("   for replacing it rather than tuning it)\n")
    print(f"  {'old score':>12}{'n':>6}{'mean timing z':>16}")
    for lo in range(0, 100, 20):
        idx = (s >= lo) & (s < lo + 20)
        if idx.sum():
            print(f"  {lo:>5}-{lo+19:<6}{int(idx.sum()):>6}{z[idx].mean():>16.4f}")
    return {"rho": float(rho), "p": float(p)}


def panel_confound(traders):
    hsep("PANEL 4 - drift confound check")
    sel = [t for t in cohort(traders, bad_only=False)
           if t["z_all"] is not None and t["n_dec"] >= MIN_DEC_WINDOW]
    lb = np.array([t["long_bias"] for t in sel])
    z = np.array([t["z_all"] for t in sel])
    rho, p = stats.spearmanr(lb, z)
    print(f"  Spearman rho(long_bias, timing z) = {rho:+.4f}  p = {p:.4f}")
    print(f"  mean long bias across traders: {lb.mean():.3f}")
    print("  Trailing-drift removal is meant to make this ~0. A strong correlation")
    print("  would mean the score is still measuring (long bias x market drift) --")
    print("  exactly the artifact that made the old contrarian signal 96.6% short.")
    return {"rho": float(rho), "p": float(p)}


def panel_scores(traders, series):
    hsep("PANEL 5 - per-trader scores with FDR control")
    sel = [t for t in cohort(traders, bad_only=False) if t["n_dec"] >= MIN_DEC_SCORE]
    print(f"  traders with >= {MIN_DEC_SCORE} decisions (non-MM, span >= {MIN_SPAN_DAYS}d): {len(sel)}")
    if not sel:
        return {"n_scorable": 0, "n_bad": 0}
    rng = np.random.default_rng(1)
    for t in sel:
        r = scoring.timeshift_null(scoring.Pooled(t["dec"], series), n_draws=500, rng=rng)
        t["p"] = r["p_worse"] if r else 1.0
        t["z_vs_null"] = r["z_vs_null"] if r else 0.0
        t["z_shrunk"] = scoring.shrink(t["z_vs_null"], t["n_dec"])
        t["badness"] = scoring.badness(t["z_shrunk"])
    qv, rej = scoring.bh_fdr([t["p"] for t in sel], q=0.10)
    for t, q, r in zip(sel, qv, rej):
        t["q"] = float(q)
        t["fdr_pass"] = bool(r)
    n_bad = sum(t["fdr_pass"] for t in sel)
    exp_fp = 0.05 * len(sel)
    print(f"  pass BH-FDR q<0.10 as badly-timed: {n_bad}")
    print(f"  (unadjusted at alpha=0.05 you would expect ~{exp_fp:.0f} false positives)")
    worst = sorted(sel, key=lambda t: t["z_vs_null"])[:12]
    print(f"\n  {'address':12}{'n_dec':>7}{'z_all':>9}{'z_null':>9}{'p':>8}{'q':>8}{'badness':>9}")
    for t in worst:
        print(f"  {t['address'][:10]:12}{t['n_dec']:>7}{t['z_all']:>9.3f}"
              f"{t['z_vs_null']:>9.2f}{t['p']:>8.3f}{t['q']:>8.3f}{t['badness']:>9}")
    return {"n_scorable": len(sel), "n_bad": n_bad}


def panel_variants(series, old_scores, clusters):
    hsep("PANEL 6 - variant comparison: opens-only vs all exposure deltas")
    res = {}
    for variant in ("open_taker", "all_taker"):
        tr, _ = build_traders(series, variant, old_scores, clusters)
        bad = cohort(tr, bad_only=True)
        print(f"\n  variant = {variant}")
        r = pooled_test(bad, series, "B", f"    bad cohort window B", n_draws=1500)
        res[variant] = r
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="open_taker", choices=("open_taker", "all_taker"))
    ap.add_argument("--skip-variants", action="store_true")
    ap.add_argument("--no-cluster-weight", action="store_true")
    args = ap.parse_args()

    series = {c: scoring.PriceSeries(hl.load_candles(c)) for c in hl.MAJORS}
    old_scores = load_old_scores()
    try:
        clusters = wallet_clusters.build()
    except Exception as e:
        print(f"(wallet clusters unavailable: {e}); treating every address as its own entity")
        clusters = {}

    hsep("PHASE 0 VALIDATION GATE")
    print(f"  variant            {args.variant}")
    print(f"  horizons scored    {list(scoring.HORIZONS)}   tradable: {list(scoring.TRADABLE)}")
    print(f"  15m                not computed -- 1h bars cannot resolve it")
    print(f"  cost assumption    {scoring.COST_BPS} bp round trip")

    traders, audit = build_traders(series, args.variant, old_scores, clusters)
    panel_contamination(traders, audit)
    res_pooled = panel_pooled(traders, series)
    res_persist = panel_persistence(traders, series)
    panel_baseline(traders)
    panel_confound(traders)
    res_scores = panel_scores(traders, series)
    if not args.skip_variants:
        panel_variants(series, old_scores, clusters)

    # --- verdict -------------------------------------------------------------
    hsep("VERDICT against the kill criteria fixed before the data was seen")
    checks = []
    if res_pooled:
        ph = res_pooled["per_horizon"]
        neg_both = all(ph[h] < 0 for h in scoring.TRADABLE)
        checks.append((f"pooled window-B mean z < 0 at BOTH {'/'.join(scoring.TRADABLE)}",
                       neg_both, "  ".join(f"{h}={ph[h]:+.4f}" for h in scoring.TRADABLE)))
        checks.append(("pooled permutation p <= 0.10", res_pooled["p_worse"] <= KILL_POOLED_P,
                       f"p={res_pooled['p_worse']:.4f}"))
        checks.append(("net edge after 10bp cost > 0", res_pooled.get("net_bps", -1) > 0,
                       f"net={res_pooled.get('net_bps', float('nan')):+.2f} bp"))
        if "control_obs" in res_pooled:
            checks.append(("target cohort times WORSE than the control cohort",
                           res_pooled["obs"] < res_pooled["control_obs"],
                           f"target {res_pooled['obs']:+.4f} vs "
                           f"control {res_pooled['control_obs']:+.4f}"))
    else:
        checks.append(("pooled test computable", False, "no result"))
    if res_persist:
        sep = res_persist["separation"]
        checks.append(("window-A bottom decile is WORSE in B than the top decile",
                       sep is not None and sep > 0,
                       f"bottom {res_persist['bottom_decile_zB']:+.4f} vs "
                       f"top {res_persist['top_decile_zB']:+.4f}"))
        checks.append(("rank persistence rho > 0", res_persist["rho"] > 0,
                       f"rho={res_persist['rho']:+.4f} p={res_persist['p']:.3f}"))
    else:
        checks.append(("persistence computable", False, "insufficient sample"))
    checks.append((f">= {KILL_MIN_SCORABLE} traders scorable at n_dec>={MIN_DEC_SCORE}",
                   res_scores["n_scorable"] >= KILL_MIN_SCORABLE,
                   f"n={res_scores['n_scorable']}"))

    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {name:<52} {detail}")
    allok = all(c[1] for c in checks)
    print("\n" + ("*** PASS - proceed to Phase 1 ***" if allok else
                  "*** FAIL - do not build Phase 1. The thesis does not survive "
                  "its own pre-registered test. ***"))

    out = Path(__file__).parent / "cache" / f"validation_{args.variant}.json"
    out.write_text(json.dumps({
        "variant": args.variant, "pooled": res_pooled, "persistence": res_persist,
        "scores": res_scores,
        "checks": [{"name": n, "pass": bool(o), "detail": d} for n, o, d in checks],
        "verdict": "PASS" if allok else "FAIL",
    }, indent=2, default=float))
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
