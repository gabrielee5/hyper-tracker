"""Minimal Hyperliquid info-endpoint client for the Phase 0 validation gate.

Deliberately standalone and synchronous: the production scorer will reuse
analyzer/core/api_client.py, but Phase 0 is a throwaway gate and a resumable
sequential fetcher is easier to reason about than the async pipeline.
"""

import gzip
import json
import time
import threading
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.hyperliquid.xyz/info"

CACHE = Path(__file__).parent / "cache"
FILLS = CACHE / "fills"
CANDLES = CACHE / "candles"

MAJORS = ("BTC", "ETH", "SOL")

# userFills carries request weight 20 against a 1200/min per-IP budget, so the
# ceiling is 60 req/min. We pace a little under that. A single 2000-fill response
# is ~1MB, so serial fetching is network-bound well below the rate cap -- hence a
# shared limiter that several worker threads draw from.
MIN_INTERVAL = 60.0 / 55

_gate = threading.Lock()
_last_call = [0.0]


def _acquire():
    with _gate:
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()


def post(payload, retries=5):
    """POST to /info with pacing and backoff. Returns None on permanent failure."""
    for attempt in range(retries):
        _acquire()
        try:
            req = urllib.request.Request(
                API,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # 429 gets a long cooldown; other HTTP errors get exponential backoff.
            time.sleep(30 if e.code == 429 else 2 ** attempt)
        except Exception:
            time.sleep(2 ** attempt)
    return None


def fetch_candles(coin, interval="1h", days=200):
    """1h candles come back ~4800 bars deep in one call, which covers the whole
    scoring window. candleSnapshot returns at most the most recent 5000 bars in
    the requested window and truncates from the START, so anything finer than 1h
    needs forward-walking pagination (see Phase 1)."""
    now = int(time.time() * 1000)
    return post({
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval,
            "startTime": now - days * 86400000,
            "endTime": now,
        },
    })


def candle_path(coin, interval):
    return CANDLES / f"{coin}_{interval}.json"


def load_candles(coin, interval="1h", days=200, refresh=False):
    p = candle_path(coin, interval)
    if p.exists() and not refresh:
        return json.loads(p.read_text())
    data = fetch_candles(coin, interval, days)
    if data:
        CANDLES.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))
    return data


def fills_path(address):
    return FILLS / f"{address}.json.gz"


def load_fills(address, refresh=False):
    """Cached userFills. Returns a list, or None if the fetch failed.

    userFills is capped at the 2000 most recent fills across all coins. For the
    cohort that matters here that spans a median of ~149 days, which is enough
    for a midpoint split; traders whose 2000 fills span only days get dropped
    downstream by the window-length filter.
    """
    p = fills_path(address)
    if p.exists() and not refresh:
        try:
            with gzip.open(p, "rt") as f:
                return json.load(f)
        except Exception:
            pass  # corrupt cache entry, refetch
    data = post({"type": "userFills", "user": address})
    if data is None:
        return None
    FILLS.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt") as f:
        json.dump(data, f)
    return data
