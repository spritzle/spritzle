# spritzled - Spritzle Daemon

`spritzled` is the daemon service for Spritzle. It manages the underlying [libtorrent](https://libtorrent.org) session, manages torrent state and resume data, handles the hook alert dispatch system, and exposes an HTTP REST API for clients (such as the `spritzle` CLI or web interfaces).

## Usage

```shell
spritzled [OPTIONS] [COMMAND] [ARGS]...
```

### Options

* `-H, --host TEXT`: Hostname or IP to listen on (default: `127.0.0.1`).
* `-p, --port INTEGER`: Port for the HTTP REST server to listen on (default: `8080`).
* `-c, --config-dir, --config_dir PATH`: Path to the configuration directory (default: `~/.config/spritzle`).
* `-l, --log-level [DEBUG|INFO|WARNING|ERROR]`: Daemon log verbosity (default: `INFO`).
* `--debug`: Enable asyncio event loop debug mode.
* `--help`: Show the help message and exit.

### Subcommands

#### `spritzled key`

Manage API keys for the daemon directly from the host.

##### `spritzled key create`
Creates a new API key (printed once to stdout) and saves its SHA-256 hash to state.

```shell
spritzled key create [-n, --name <name>] [-c, --config-dir <path>]
```

##### `spritzled key list`
Lists all active and revoked API keys.

```shell
spritzled key list [-c, --config-dir <path>]
```

##### `spritzled key revoke`
Revokes an active API key by ID or name.

```shell
spritzled key revoke <id_or_name> [-c, --config-dir <path>]
```

---

## Configuration & Storage

By default, all runtime configuration and persistent state are organized according to XDG base directories:

### File Layout

**Configuration (`~/.config/spritzle/` or `-c / --config-dir`):**
* `daemon.toml`: TOML file containing daemon configuration settings.
* `spritzled.lock`: Exclusive file lock (`flock`) ensuring only one daemon process runs per configuration directory.
* `hooks/`: Directory containing user-defined hook executables triggered by libtorrent alerts. See [hooks documentation](hooks.md) for details.

**State (`~/.local/share/spritzle/state/`):**
* `identity`: Contains the persistent `daemon_id` used by clients to verify daemon identity.
* `keys.json`: Stored SHA-256 hashes and metadata for API keys.
* `local_remote.json`: Discovery file written on daemon startup containing connection details (`url`), daemon identifier (`daemon_id`), and auto-generated API key (`api_key`) for local CLI clients (file mode `0600`).
* `session.state`: Bencoded libtorrent session state, restored on startup and saved on clean shutdown.
* `<info_hash>.resume`: Fastresume metadata file for each active torrent.

### Key Configuration Settings (`daemon.toml`)

Daemon-level configuration values can be inspected or modified at runtime via the REST API (`/config`) or using `spritzle daemon-config`, or edited directly in `daemon.toml`.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `add_torrent_params.save_path` | string | `~/Downloads` | Default directory where downloaded files are saved. |
| `save_resume_data_interval` | int | `60` | Interval in seconds between automatic background resume data flushes. |

> [!NOTE]
> Daemon configuration in `daemon.toml` is distinct from **libtorrent session settings** (such as `listen_interfaces`, `download_rate_limit`, `connections_limit`, etc.). Libtorrent session settings are preserved in `session.state` across restarts and can be inspected or adjusted at runtime via the REST API (`/session/settings`) or the CLI command `spritzle settings`.

For detailed information on configuring clients and third-party integrations, see the [remotes documentation](remotes.md).


---

## Running as a Systemd Service

To run `spritzled` as a user service under systemd, create `~/.config/systemd/user/spritzled.service`:

```ini
[Unit]
Description=Spritzle BitTorrent Daemon
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/spritzled --config-dir %h/.config/spritzle --port 8080 --log-level INFO
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Enable and start the service:

```shell
systemctl --user daemon-reload
systemctl --user enable --now spritzled
```

Check service status and logs:

```shell
systemctl --user status spritzled
journalctl --user -u spritzled -f
```

---

## Process Lifecycle & Signals

`spritzled` handles process signals gracefully to ensure no download progress, resume data, or configuration is lost:

* **Graceful Shutdown (`SIGINT`, `SIGTERM`, or `DELETE /core`):**
  1. Stops the alert monitoring loop.
  2. Flushes in-flight fastresume data (`<info_hash>.resume`) for all active torrents to disk.
  3. Bencodes and saves libtorrent session state to `session.state`.
  4. Releases the advisory file lock (`spritzled.lock`) and closes HTTP listener sockets.

* **Single Instance Guarantee:**
  * An exclusive non-blocking advisory file lock (`flock`) on `~/.config/spritzle/spritzled.lock` ensures only one daemon instance runs per configuration directory.
  * If another instance is already running, `spritzled` exits immediately with code 1.
