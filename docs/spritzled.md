# <img src="assets/logo-icon.svg" alt="Spritzle" width="28" height="28" align="center" /> spritzled - Spritzle Daemon

`spritzled` is the daemon service for Spritzle. It manages the underlying [libtorrent](https://libtorrent.org) session, manages torrent state and resume data, handles the hook alert dispatch system, and exposes an HTTP REST API for clients (such as the `spritzle` CLI or web interfaces).

## Usage

```shell
spritzled [OPTIONS] [COMMAND] [ARGS]...
```

### Options

* `-H, --host TEXT`: Hostname or IP to listen on (default: `127.0.0.1`, env: `SPRITZLE_HOST`).
* `-p, --port INTEGER`: Port for the HTTP REST server to listen on (default: `17382`, env: `SPRITZLE_PORT`).
* `-c, --config-dir, --config_dir PATH`: Path to the configuration directory (default: `~/.config/spritzle`, env: `SPRITZLE_CONFIG_DIR`).
* `-s, --state-dir, --state_dir PATH`: Path to the state directory for persistent data (resume files, keys, identity; default: `~/.local/share/spritzle/state`, env: `SPRITZLE_STATE_DIR`).
* `-l, --log-level [DEBUG|INFO|WARNING|ERROR]`: Daemon log verbosity (default: `INFO`, env: `SPRITZLE_LOG_LEVEL`).
* `-i, --listen-interfaces TEXT`: Network interface and port to bind for BitTorrent swarm traffic (default: libtorrent default, env: `SPRITZLE_LISTEN_INTERFACES`; e.g. `tun0:6881` or `wg0:6881`).
* `--debug`: Enable asyncio event loop debug mode.
* `--help`: Show the help message and exit.

### Subcommands

#### `spritzled key`

Manage API keys for the daemon directly from the host.

##### `spritzled key create`
Creates a new API key (printed once to stdout) and saves its SHA-256 hash to state.

```shell
spritzled key create [-n, --name <name>] [-c, --config-dir <path>] [-s, --state-dir <path>]
```

##### `spritzled key list`
Lists all active and revoked API keys.

```shell
spritzled key list [-c, --config-dir <path>] [-s, --state-dir <path>]
```

##### `spritzled key revoke`
Revokes an active API key by ID or name.

```shell
spritzled key revoke <id_or_name> [-c, --config-dir <path>] [-s, --state-dir <path>]
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
| `default_save_path` | string | `~/Downloads` | Default directory where downloaded files are saved. Defaults to `$SPRITZLE_SAVE_PATH`, `$SPRITZLE_DOWNLOAD_DIR`, or `~/Downloads`. Spritzled auto-creates the directory on startup and validates write permissions. |
| `save_resume_data_interval` | int | `60` | Interval in seconds between automatic background resume data flushes. |
| `config_watch_interval` | float | `2.0` | Interval in seconds between file watcher polling checks for `daemon.toml` modifications. Set to `0` or negative to disable file watching. |
| `listen_interfaces` | string | `""` | Network interfaces and ports to bind for BitTorrent swarm traffic (e.g. `tun0:6881`). When defined, overrides libtorrent defaults on startup and config reload. |
| `log_level` | string | `"INFO"` | Logging verbosity level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). Dynamically applied on config change or reload. |
| `log_buffer_size` | int | `1000` | Maximum number of structured log records stored in the in-memory ring buffer served by `GET /log` and `spritzle logs`. |
| `state_dir` | string | `""` | Directory for persistent daemon state (resume data, keys, identity). When not specified, defaults to `$SPRITZLE_STATE_DIR` or `~/.local/share/spritzle/state`. |

### Configuration Reloading & Live Watching

`spritzled` supports dynamic configuration reloads without restarting the process:
* **Automatic File Watching**: An asynchronous background watcher checks `daemon.toml` for external modifications every `config_watch_interval` seconds (`2.0s` by default). Valid configuration changes are dynamically applied to the running daemon.
* **SIGHUP Reload**: Sending `SIGHUP` to the daemon process (`kill -HUP $PID` or `systemctl --user reload spritzled`) triggers an immediate configuration reload from disk.
* **API / CLI Reload**: Call `POST /config/reload` or run `spritzle daemon-config --reload` to trigger an on-demand reload.
* **Syntax Safety**: If an external edit contains syntax errors or invalid TOML, the reload safely fails, logs an error, and preserves the active running configuration without corruption.

> [!NOTE]
> Daemon configuration in `daemon.toml` is distinct from **libtorrent session settings** (such as dynamic rate limits or connection counts). Libtorrent session settings are preserved in `session.state` across restarts and can be inspected or adjusted at runtime via the REST API (`/session/settings`) or the CLI command `spritzle settings`.

For detailed information on configuring clients and third-party integrations, see the [remotes documentation](remotes.md).

---

## Running with Docker & VPN

Spritzle provides an official lightweight container image for `spritzled` with native support for Docker Compose and Gluetun VPN leak protection (`tun0`).
See the [Docker documentation](docker.md) for complete setup instructions and VPN templates.


---

## Running as a Systemd Service

To run `spritzled` as a user service under systemd, create `~/.config/systemd/user/spritzled.service`:

```ini
[Unit]
Description=Spritzle BitTorrent Daemon
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/spritzled --config-dir %h/.config/spritzle --port 17382 --log-level INFO
ExecReload=/bin/kill -HUP $MAINPID
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
