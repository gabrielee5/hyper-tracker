"""Phase 0 step 1: populate the fill/candle cache. Resumable; safe to re-run.

Sample = every trader the existing PnL score calls bad (score<=5), plus a
stratified control spread across the whole score range so the new metric can be
compared against the old one rather than only described.

Run in the background; it paces at ~55 req/min to stay inside the info-endpoint
weight budget, so a full sweep is roughly 45 minutes.
"""

import argparse
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import hl

ROOT = Path(__file__).resolve().parent.parent
SCORED_DB = ROOT / "data" / "analyzed_traders.db"


def pick_sample(control_per_bucket=90):
    con = sqlite3.connect(f"file:{SCORED_DB}?mode=ro", uri=True)
    bad = [r[0] for r in con.execute(
        "SELECT address FROM scored_traders WHERE score <= 5 ORDER BY address"
    )]
    control = []
    # Stratify the control across score deciles. The top buckets matter most:
    # they are the traders the old score calls *good*, and the pilot suggested
    # they are no better timed than the bad ones.
    for lo in range(0, 100, 10):
        control += [r[0] for r in con.execute(
            "SELECT address FROM scored_traders WHERE score >= ? AND score < ? "
            "ORDER BY address LIMIT ?", (lo, lo + 10, control_per_bucket)
        )]
    con.close()
    seen, out = set(), []
    for a in bad + control:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out, set(bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap addresses (0 = all)")
    ap.add_argument("--refresh", action="store_true", help="ignore existing cache")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    for coin in hl.MAJORS:
        c = hl.load_candles(coin, "1h", 200, refresh=args.refresh)
        print(f"candles {coin} 1h: {len(c) if c else 'FAILED'}", flush=True)

    addrs, bad = pick_sample()
    if args.limit:
        addrs = addrs[:args.limit]
    print(f"sample: {len(addrs)} addresses ({len(bad)} flagged bad by old score)", flush=True)

    todo = [a for a in addrs if args.refresh or not hl.fills_path(a).exists()]
    print(f"cached already: {len(addrs) - len(todo)} | to fetch: {len(todo)}", flush=True)

    t0 = time.time()
    state = {"done": 0, "fails": 0}
    lock = threading.Lock()

    def work(a):
        ok = hl.load_fills(a, refresh=args.refresh) is not None
        with lock:
            state["done"] += 1
            if not ok:
                state["fails"] += 1
            i = state["done"]
            if i % 25 == 0 or i == len(todo):
                el = time.time() - t0
                eta = (el / i) * (len(todo) - i) / 60
                print(f"  {i}/{len(todo)} fetched | {state['fails']} failed | "
                      f"{el/i:.2f}s/addr | ETA {eta:.0f}m", flush=True)

    # Workers only hide network latency; the shared limiter in hl.post still caps
    # the actual request rate at 55/min.
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(work, todo))
    fails = state["fails"]

    print(f"DONE. cached={sum(1 for a in addrs if hl.fills_path(a).exists())}/{len(addrs)} "
          f"failed={fails}", flush=True)


if __name__ == "__main__":
    main()
