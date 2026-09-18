"""Collapse addresses that are really one entity before counting them as evidence.

A naive version of this is badly misleading. data/contrarian_signals.db has
120,728 groups of (timestamp, coin, side, size) shared by 2+ addresses, which
looks like massive copy-trading -- but 82% of those groups have a position size
rounded to 2 decimals or fewer (39% are whole numbers). Two unrelated traders
both holding exactly 1.0 ETH at the same snapshot is a coincidence, not a
relationship, and taking the transitive closure over those coincidences merges
1,569 wallets into one meaningless cluster.

So two addresses are treated as the same entity only if they share a position
with a NON-ROUND size (>2 decimals) on at least MIN_COOCCUR distinct occasions.
That reduces 120,728 raw groups to 280 credible pairs over 222 addresses -- real,
worth correcting for, and about two orders of magnitude smaller than the raw
count suggests.
"""

import itertools
import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIGNALS_DB = ROOT / "data" / "contrarian_signals.db"
CACHE = Path(__file__).parent / "cache" / "wallet_clusters.json"

MIN_COOCCUR = 20     # repeated co-occurrence, not a one-off coincidence

# Non-round size: not expressible in 2 decimals. Keeps round-number collisions out.
DUP_QUERY = """
SELECT group_concat(DISTINCT address) FROM position_snapshot
 GROUP BY timestamp, coin, side, size
HAVING count(DISTINCT address) > 1
   AND abs(size * 100 - CAST(size * 100 AS INT)) > 1e-9
"""


def _find(parent, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def build(refresh=False):
    """-> {address: cluster_id}. Addresses absent from the map are singletons."""
    if CACHE.exists() and not refresh:
        return json.loads(CACHE.read_text())

    con = sqlite3.connect(f"file:{SIGNALS_DB}?mode=ro", uri=True)
    pair_counts = Counter()
    for (blob,) in con.execute(DUP_QUERY):
        if not blob:
            continue
        addrs = sorted(set(blob.split(",")))
        for x, y in itertools.combinations(addrs, 2):
            pair_counts[(x, y)] += 1
    con.close()

    strong = [p for p, c in pair_counts.items() if c >= MIN_COOCCUR]
    parent = {}
    for x, y in strong:
        parent.setdefault(x, x)
        parent.setdefault(y, y)
    for x, y in strong:
        rx, ry = _find(parent, x), _find(parent, y)
        if rx != ry:
            parent[ry] = rx

    out = {a: _find(parent, a) for a in parent}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out))
    return out


def sizes(clusters):
    return Counter(clusters.values())


if __name__ == "__main__":
    c = build(refresh=True)
    s = sizes(c)
    print(f"addresses in a multi-wallet cluster: {len(c)}")
    if s:
        print(f"clusters: {len(s)} | largest: {max(s.values())} wallets "
              f"| mean size: {sum(s.values())/len(s):.1f}")
        print("cluster size distribution:", dict(sorted(Counter(s.values()).items())))
