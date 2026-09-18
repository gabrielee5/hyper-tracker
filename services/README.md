# services

launchd units for running parts of the pipeline unattended.

**macOS only.** These use `launchctl` and `caffeinate`. On Linux you would want
systemd units instead; the commands each service runs are in the plist
templates and translate directly.

## Two groups

**Scout** — `fetcher` + `analyzer`, the data collection half. The fetcher runs
15 minutes at the top of each hour; the analyzer runs continuously, because it
is rate-limited to 100–200 traders/hour and always has a backlog.

**Contrarian** — the signal generation half, running continuously.

They are independent. Running scout alone is the useful configuration if you
just want to accumulate data.

## Usage

```bash
cd services

./start-scout.sh              # fetcher (hourly) + analyzer (continuous)
./start-scout.sh --minute 30  # run the fetcher at :30 instead of :00
./status-scout.sh
./stop-scout.sh

./start-services.sh           # contrarian
./status-services.sh
./stop-services.sh
./restart-services.sh
```

Starting either group also runs `caffeinate -s` to stop the Mac sleeping, since
a sleeping machine collects no data. Its PID is kept in `.caffeinate.pid` /
`.caffeinate-scout.pid` and the stop scripts kill it, re-enabling normal sleep.
**If you kill the scripts some other way, that caffeinate process survives** and
your Mac will not sleep until you kill it by hand.

Once started, a service keeps running across terminal close, logout and reboot
until you stop it.

## How the plists work

`com.hyper-tracker.{fetcher,analyzer,contrarian}.plist` are **templates**, not
loadable files. They contain the literal string `__PROJECT_ROOT__`, which the
start scripts substitute with the repo path when installing into
`~/Library/LaunchAgents/`. `start-scout.sh` additionally rewrites the fetcher's
schedule minute.

Do not `launchctl load` the files in this directory directly — load the
installed copies in `~/Library/LaunchAgents/`.

This is why the repo contains no absolute paths: the units work from wherever
you cloned it, under whatever username.

`run-fetcher.sh` is the wrapper the fetcher unit invokes. It activates the venv,
starts `pipeline/fetcher/main.py`, and sends SIGTERM after 900 seconds for a
graceful shutdown, treating exit code 143 as success.

## Logs

```
logs/fetcher-stdout.log     logs/fetcher-stderr.log
logs/analyzer-stdout.log    logs/analyzer-stderr.log
logs/contrarian-stdout.log  logs/contrarian-stderr.log
```

**These grow without bound.** There is no rotation on the launchd side, and the
contrarian logs reached 259MB each over the life of this project. Truncate them
periodically or add rotation.

## Prerequisites

- a venv at the repo root with `requirements.txt` installed — the units invoke
  `venv/bin/python3` directly, not whatever is on `PATH`
- for the contrarian unit, `data/analyzed_traders.db` must already have scored
  traders in it; the analyzer has to have run first

## Before you rely on this

The pipeline these units keep alive does not produce a tradable signal — see
[`../README.md`](../README.md#what-it-found). Running it continuously makes
sense for collecting data, which is what it was ultimately used for, not for
acting on the output.
