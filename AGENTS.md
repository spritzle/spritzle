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
- **CLI event loop integration**: Never invoke `asyncio.run()` inside CLI client wrappers (`Client.do_command()`). Tests using `CliRunner` share the thread's event loop with the in-process `aiohttp` server. Reuse `asyncio.get_event_loop().run_until_complete(...)` so test server sockets can be serviced during CLI requests without deadlock.
- **Config typing in background tasks**: Values retrieved from `Config` (SQLite/JSON) are not type-guaranteed. Always safely coerce numeric config values (e.g. `float(config.get("...", 60))`) before passing them to APIs like `asyncio.sleep()`. Guard periodic loops against unhandled type or value errors to prevent permanent background task death.

## 3. API & Data State Conventions
- **Info-hashes**: Torrent handles use 20-byte SHA-1 info-hashes (40 hex characters). Always key `core.torrent_data` and resume data files on `str(torrent_handle.info_hash())`.
- **No speculative mutation**: Staged metadata (such as torrent tags or config updates) must only be committed to persistent state after the corresponding libtorrent or database operation succeeds.
- **Atomic config mutations**: `DB.__setitem__` commits immediately to SQLite per key. Endpoints applying bulk or partial updates (`PUT /config`, `PATCH /config`) must snapshot existing keys and explicitly roll back (restore modified keys and delete newly added keys) if an exception occurs mid-update.
- **Ingress metadata validation**: Custom metadata accepted via API (e.g. `spritzle.tags`) must be strictly validated at ingestion time (`POST /torrent`). Ensure `tags` is normalized to a `list[str]` (defaulting `None` to `[]`). Downstream consumers (such as shell hook runners joining tags with commas) must never receive `None` or non-string elements.
- **Query engine consistency**: In `get_torrent_list_by_query()`, ensure any unhandled type or `None` value defaults to non-matching (break) unless `op == "ne"`. Every data type branch (`str`, `bool`, numeric, `list`) must explicitly validate `op` against its supported operators and raise `HTTPBadRequest(400)` for unsupported ones. Ensure `op == "ne"` breaks on match and continues on non-match across all types.
- **Bulk operations**: In `DELETE /torrent`, separate `lt.options_t` keys (like `delete_files`) from query filters so filtered deletions only target matching torrents.
- **Loopback & IPv6 URI formatting**: Always account for IPv6 loopback (`::1`) in host allowlists alongside IPv4 (`127.0.0.1`). When constructing HTTP URLs from host variables, bracket IPv6 literal addresses (`http://[{host}]:{port}/...`) per RFC 3986 so URL parsers do not treat colons as port separators.
- **Middleware body decoding**: Logging or debugging middlewares must never assume request bodies are valid UTF-8. Catch `UnicodeDecodeError` when awaiting `request.text()` so malformed payloads reach request handlers and return HTTP 400 instead of crashing into HTTP 500.

