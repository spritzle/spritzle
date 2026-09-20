# Changelog

All notable changes to Spritzle are documented in this file.

## [1.0.0] - 2026-09-19

Initial release of Spritzle, a lightweight BitTorrent client built around `libtorrent-rasterbar`.

### Features

#### Daemon (`spritzled`)
* **Libtorrent Integration**: Session management, fastresume data persistence, bandwidth limits, listen interfaces, piece priority, and sequential download support.
* **REST API**: HTTP API for managing torrents, session settings, daemon configuration, API keys, and server lifecycle.
* **Alert & Hook System**: Extensible hook runner triggered by libtorrent status alerts (e.g. `torrent_finished_alert`, `state_changed_alert`, `torrent_error_alert`) passing info-hash and tag metadata.
* **Security & Authentication**:
  * Scoped API keys with SHA-256 state hashing (`spritzled key create/list/revoke`).
  * Daemon identity tracking (`daemon_id`) and `X-Spritzle-Daemon-Id` header verification.
  * Zero-config local discovery via permissions-isolated `local_remote.json` (`0600`).
  * Ingress SSRF protection blocking loopback and private subnets by default on URL torrent addition.
* **Single Instance Guarantee**: Advisory file lock (`flock`) on configuration directory to prevent concurrent daemon conflicts.
* **Robust State Persistence**: Atomic config updates with automatic rollback, resilient resume data flushing, and safe shutdown lifecycle handling `SIGINT`/`SIGTERM`.

#### CLI Client (`spritzle`)
* **Commands**:
  * `spritzle add`: Add torrents via local files, magnet links, or remote HTTP/HTTPS URLs with optional tags, paused status, file prioritization, and `--watch` live tracking.
  * `spritzle list`: Tabular overview of active torrents with custom column selection (`--keys`), query filtering (`name`, `state`, `tags`), and `--watch` continuous updates.
  * `spritzle top`: Live dashboard displaying session speed gauges, transfer stats, and torrent tables.
  * `spritzle info`: Detailed inspector for metadata, trackers, peers, file lists, pieces, and progress.
  * `spritzle pause` / `spritzle resume`: Batch torrent state control with semaphore-bounded concurrency.
  * `spritzle remove`: Remove torrents with optional data deletion (`--delete-files`) and query matching.
  * `spritzle move-storage`: Relocate torrent download directories dynamically.
  * `spritzle flags`: Inspect and toggle torrent flags (sequential download, auto-managed, super-seeding, DHT, etc.).
  * `spritzle settings`: Inspect and modify libtorrent session settings with typed validation.
  * `spritzle stats`: Global transfer rates, payload counters, DHT node count, and connection metrics.
  * `spritzle remote`: Manage remote daemon profiles, TLS options (CA certs, pinned SHA-256 fingerprints, insecure mode), and daemon identity checks.
  * `spritzle config` & `spritzle daemon-config`: Manage client-side preferences and server configurations independently.
  * `spritzle completion`: Output and install shell completion scripts.
* **Script & Machine Friendliness**: Full support for `--plain` (delimiter-separated for scripting) and `--json` outputs, automatic TTY color detection, and standard non-zero exit codes.
