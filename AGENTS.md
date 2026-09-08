# Developer & Agent Guidelines for Spritzle

## 1. Tooling & Environment
- Always execute commands via `uv run` to ensure dependencies and native `libtorrent` extensions are loaded:
  - Run test suite: `uv run pytest`
  - Run specific test: `uv run pytest tests/path/to/test.py`
  - Linting: `uv run ruff check`
  - Type checking: `uv run ty check`
- Tests involve real libtorrent sessions; expect full runs to take ~60–90 seconds.

## 2. Concurrency & Libtorrent Rules
- **Multi-waiter alerts**: When multiple callers await a libtorrent alert, track per-caller futures in a `set`. Never share a single future directly if a caller cancellation could abort it for other callers.
- **Retain background tasks**: Never fire-and-forget `asyncio.create_task()` without saving a strong reference to the task in an instance set (e.g. `self._tasks.add(t)` with `t.add_done_callback(self._tasks.discard)`), to prevent Python's garbage collector from dropping active coroutines.
- **Executor write isolation**: When dispatching resume-data or disk I/O to executors, bind the task to its specific `Future` instance rather than popping by hash name in `finally:`.
- **Alert lifetime**: Do not call `session.pop_alerts()` while previous alert handlers are still executing; libtorrent invalidates alert pointers upon the next pop.

## 3. API & Data State Conventions
- **Info-hashes**: Torrent handles use 20-byte SHA-1 info-hashes (40 hex characters). Always key `core.torrent_data` and resume data files on `str(torrent_handle.info_hash())`.
- **No speculative mutation**: Staged metadata (such as torrent tags or config updates) must only be committed to persistent state after the corresponding libtorrent or database operation succeeds.
- **Query matching**: In `get_torrent_list_by_query()`, ensure any unhandled type or `None` value defaults to non-matching (break) unless `op == "ne"`.
- **Bulk operations**: In `DELETE /torrent`, separate `lt.options_t` keys (like `delete_files`) from query filters so filtered deletions only target matching torrents.
- **Loopback**: Always account for IPv6 loopback (`::1`) in host allowlists alongside IPv4 (`127.0.0.1`).
