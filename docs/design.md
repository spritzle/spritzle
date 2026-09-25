# <img src="assets/logo-icon.svg" alt="Spritzle" width="28" height="28" align="center" /> Architecture & Design

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

CLI Visual Presentation Architecture
-------------------------------------

* **Decoupled Client Runtime:** The CLI is a pure-Python HTTP client without native dependencies or `libtorrent` imports.
* **Dual-Mode Output Pipeline:**
  * **Interactive TTY Mode:** Emits modern Rich-formatted output with muted dim borders, semantic status pills (`● downloading`, `● seeding`, `⏸ paused`, `✖ error`), transfer rate color differentiation (bright green download, cyan upload, dim idle), and high-resolution smooth Unicode progress bars (`━`).
  * **Script & Machine Mode:** Automatically suppresses ANSI escape sequences, colors, and progress bars when piped, redirected, run without a TTY, or when `NO_COLOR` / `--plain` / `--json` is provided. Delivers deterministic, delimiter-friendly tabular data or JSON.
* **Theme System:**
  * Configured via `spritzle config theme <modern|minimal|ascii>`.
  * `modern`: Rounded borders (`box.ROUNDED`), dim frame styling, status pills, smooth progress bars.
  * `minimal`: Horizontal boundary dividers (`box.HORIZONTALS`), dim accents.
  * `ascii`: Strict ASCII framing (`box.ASCII`), unstyled borders for terminal environments without Unicode support.
* **Multi-Section Cards & Views:**
  * Detailed single-torrent inspector (`spritzle info`) organized into Transfer, Swarm, Storage, and Configuration panels.
  * Session metrics (`spritzle stats`) rendered as a balanced multi-panel grid (Torrents, Transfer, Swarm, DHT).
  * Daemon status (`spritzle status`) and remote management (`spritzle remote status`) structured with latency indicators and connection cards.
  * Action feedback cards for torrent ingestion (`spritzle add`) and helpful empty states (`spritzle list`).


