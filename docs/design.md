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
    |HTTP Request|                               |HTTP Response
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
