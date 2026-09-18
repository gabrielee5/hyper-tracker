# archive

Historical artifacts. **Not current, not maintained, and not a guide to how the
project works today.** Kept because they contain specific findings that are
still traceable in the code.

For current documentation start at [`../../README.md`](../../README.md).

## `CODE_REVIEW_REPORT.md`

An automated code review dated 2025-12-19, covering fetcher, analyzer,
contrarian and simulator. It predates `follower/`, `observer/`, `market_makers/`
and `execution_analyzer/` entirely, and the directory layout it describes is the
pre-`pipeline/` one.

No record was kept of which of its 94 findings were fixed, so treat every one as
unverified. Two are worth knowing about because they were later confirmed
independently:

- the simulator Sharpe bug at `performance_tracker.py:65`, which the project
  notes reached separately;
- thread-safety of the shared SQLite connections in the dashboard layers.

Its "Testing Gaps" sections describe test files that were never written. The
only test suite in this repo is `tests/test_execution_scoring.py`.
