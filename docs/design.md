Design
======

Files & Layout
--------------

Spritzle organizes runtime configuration and persistent state according to XDG base directories:

* **Configuration (`~/.config/spritzle/`):**
  * `cli.toml`: Client preferences (managed via `spritzle config`).
  * `remotes.toml`: Remote daemon profiles, endpoints, and credentials (mode 0600, managed via `spritzle remote`).
  * `daemon.toml`: Daemon configuration settings (managed via `spritzle daemon-config` or `/config`).
  * `spritzled.lock`: Exclusive lock file preventing concurrent daemon instances on the same config path.
  * `hooks/`: User-defined hook executables triggered by libtorrent alerts.

* **State (`~/.local/share/spritzle/state/`):**
  * `identity`: Persistent daemon identifier (`daemon_id`).
  * `keys.json`: Stored SHA-256 hashes and metadata for API keys.
  * `local_remote.json`: Zero-config local discovery metadata (mode 0600).
  * `session.state`: Bencoded libtorrent session state saved on clean shutdown and restored on startup.
  * `<info_hash>.resume`: Fastresume metadata file for each active torrent.

Request Lifetime
----------------

```

    +------------+                               +------------+
    |HTTP Request|                               |HTTP Response|
    +-----+------+                               +------------+
          |                                            ^
          |                                            |
          v                                            |
    +------------+                               +-----+------+
    | MIDDLEWARE |                               | MIDDLEWARE |
    |------------|                               |------------|
    |Auth & debug|                               |Attach      |
    |validation, |                               |daemon id & |
    |decode JSON |                               |JSON encode |
    +-----+------+                               +------------+
          |                                            ^
          |                                            |
          v                                            |
    +------------+         +-----------+         +-----+------+
    |  RESOURCE  |         |    CORE   |         |  RESOURCE  |
    |------------|         |-----------|         |------------|
    |Validate &  |         |Perform    |         |Format data |
    |normalize   +-------->|libtorrent +-------->|into JSON   |
    |arguments   |         |operations |         |response    |
    +------------+         +-----------+         +------------+
```

Core Architecture & Subsystems
------------------------------

* **Core Engine (`spritzle.daemon.core`):**
  Acts as the central daemon orchestrator. Manages the lifecycle of the native `libtorrent.session`, session state restoration, and coordinates all sub-components.

* **Alert Dispatcher (`spritzle.daemon.alert`):**
  A continuous background asyncio task that monitors `libtorrent.session.wait_for_alert()`, drains alerts with `pop_alerts()`, and dispatches typed alert instances to registered callbacks (such as session stats, status changes, and hook triggers).

* **Resume Data Engine (`spritzle.daemon.resume_data`):**
  Periodically and on-demand saves torrent fastresume files (`<info_hash>.resume`). Offloads blocking disk I/O to a background thread pool executor so disk operations never stall network transfers or the REST API.

* **Hook Dispatcher (`spritzle.daemon.hooks`):**
  Asynchronously invokes user-defined scripts in `~/.config/spritzle/hooks/` whenever `status_notification` alerts fire (such as torrent completion), passing info-hashes and metadata tags.

* **Client & Remote Isolation:**
  * Client preferences reside exclusively in `cli.toml` (`CLIConfig`).
  * Remote daemon endpoints and credentials reside in `remotes.toml` (`RemotesConfig`, mode `0600`).
  * Daemon-level settings reside in `daemon.toml` (`Config`).
  * Libtorrent session settings are preserved in binary `session.state`.

