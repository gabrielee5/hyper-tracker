# fetcher

Subscribes to Hyperliquid's live trade feed and records the address behind every
fill. This is the front of the pipeline — everything downstream works from the
address pool it builds.

## What it does

Opens a WebSocket to `wss://api.hyperliquid.xyz/ws`, subscribes to trades for
the configured coins, and extracts the counterparty addresses from each fill.
Addresses are buffered (`BATCH_SIZE`, default 1000) and written in batches, with
a deduplication pass every `DEDUP_INTERVAL` seconds. It reconnects
automatically.

`TRACK_ROLE` looks like it filters by maker or taker. **It does not** — both
addresses are always recorded. The public `trades` subscription does not carry
the `crossed` field that distinguishes the two, so the role is not knowable from
this feed. The setting is validated and then ignored. See
[`../../docs/TRACK_ROLE_GUIDE.md`](../../docs/TRACK_ROLE_GUIDE.md) for why the
distinction still matters and where it gets applied instead
(`research/execution_analyzer/`, from `userFills`, which does carry `crossed`).

It writes two tables. `addresses` is the one that matters — the deduplicated
pool, with per-address trade counts and volume. `trades` records the raw fills
but **nothing downstream reads it**: the WebSocket only sees trades from the
moment you connect, so it cannot support a retrospective analysis. The analyzer
re-fetches each trader's full history from the REST API instead.

## Run

```bash
cd pipeline/fetcher
python main.py
```

**Must be started from its own directory** — `DATABASE_PATH` is relative to it.
Stop with Ctrl-C; it flushes the buffer on shutdown.

Dashboard on `http://localhost:5000`: live trade rate, address count, top
addresses by volume, and connection status.

## Configuration

The repo-root `.env`. Copy `.env.example` to `.env` — the defaults work. Full
reference in [`../../docs/CONFIGURATION.md`](../../docs/CONFIGURATION.md).

The settings that matter are `SELECTED_COINS` (or `TRACK_ALL_COINS=true`) and
`BATCH_SIZE`.

## How long to run it

Longer than you expect. The address pool is only useful once it is large enough
that the analyzer has a meaningful sample to work through, and the analyzer only
processes 100–200 traders/hour. The reference dataset here reached 114,487
addresses by running 15 minutes out of every hour for several months — see
[`../../services/`](../../services/) for the launchd units that did that.

## Inspecting the data

```bash
cd pipeline/fetcher
python query_addresses.py     # statistics, top traders by volume and trade count
python export_addresses.py    # full address table -> exports/addresses_export_<ts>.csv
```

Both resolve their own paths, so they work from anywhere.

More in [`../../docs/DATA_ACCESS.md`](../../docs/DATA_ACCESS.md).

## Files

| file | |
|---|---|
| `main.py` | orchestrator and entry point |
| `config.py` | Pydantic-validated settings from `.env` |
| `connection.py` | WebSocket lifecycle and reconnection |
| `address_tracker.py` | address extraction and batching |
| `storage.py` | SQLite writes and queries |
| `dashboard.py` | Flask dashboard (HTML inline, not a template file) |
| `utils.py` | logging setup |
