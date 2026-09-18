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
spritzled key create [--name <name>]
```

##### `spritzled key list`
Lists all active and revoked API keys.

```shell
spritzled key list
```

##### `spritzled key revoke`
Revokes an active API key by ID or name.

```shell
spritzled key revoke <id_or_name>
```

---

## Configuration & Storage

By default, all runtime configuration and persistent state are stored in `~/.config/spritzle/` (or the directory passed via `-c / --config-dir`).

### File Layout

Daemon configuration and state are organized according to XDG base directories:

**Configuration (`~/.config/spritzle/` or `-c / --config-dir`):**
* `daemon.toml`: TOML file containing daemon configuration settings.
* `spritzled.lock`: Exclusive file lock (`flock`) ensuring only one instance runs per configuration directory.
* `hooks/`: Directory containing user-defined hook executables triggered by libtorrent alerts. See [hooks documentation](hooks.md) for details.

**State (`~/.local/share/spritzle/state/`):**
* `identity`: Contains the persistent `daemon_id` used by clients to verify daemon identity.
* `keys.json`: Stored SHA-256 hashes and metadata for API keys.
* `local_remote.json`: Discovery file containing connection details and API key for local CLI clients (mode 0600).
* `session.state`: Bencoded libtorrent session state, restored on startup and saved on clean shutdown.
* `<info_hash>.resume`: Fastresume metadata file for each active torrent.

### Key Configuration Settings

Configuration values can be inspected or modified at runtime via the REST API (`/config`) or using `spritzle daemon-config`, or edited directly in `daemon.toml`.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `add_torrent_params.save_path` | string | `~/Downloads` | Default directory where downloaded files are saved. |
| `listen_interfaces` | string | `"0.0.0.0:6881"` | libtorrent network interfaces and ports to bind to. |
| `save_resume_data_interval` | int | `60` | Interval in seconds between automatic background resume data flushes. |

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
