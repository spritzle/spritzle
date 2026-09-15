# spritzle - Command-Line Interface

`spritzle` is the command-line client for managing and interacting with a running `spritzled` daemon.

## Usage

```shell
spritzle [OPTIONS] COMMAND [ARGS]...
```

### Global Options

* `-h, --host TEXT`: Hostname or IP address of the `spritzled` daemon (default: `127.0.0.1`). Both IPv4 and IPv6 (e.g. `::1`) are supported.
* `-p, --port INTEGER`: Port of the `spritzled` daemon (default: `8080`).
* `-c, --config PATH`: Local configuration directory (default: `~/.config/spritzle`).
* `-t, --token TEXT`: Explicit JWT authorization token.
* `--help`: Show the help message and exit.

### Environment Variables

All global options can be set via environment variables prefixed with `SPRITZLE_`:
* `SPRITZLE_HOST`: Daemon hostname or IP.
* `SPRITZLE_PORT`: Daemon port number.
* `SPRITZLE_CONFIG`: Local configuration directory path.
* `SPRITZLE_TOKEN`: JWT authentication token.

---

## Authentication & Tokens

When authenticating against a remote `spritzled` daemon that requires authentication:

```shell
spritzle auth
```

Prompts for the daemon password, queries `POST /auth`, and stores the returned JWT in `~/.config/spritzle/tokens` keyed by `host:port`. Subsequent CLI commands automatically load and send this token.

Alternatively, you can provide the token via `--token` or `SPRITZLE_TOKEN`, or generate one on the daemon host using `spritzled token`.

---

## Command Reference

### `add` - Add a Torrent

Adds a torrent by file path, HTTP URL, or info-hash.

```shell
spritzle add [OPTIONS] URL_OR_FILE
```

Options:
* `-t, --tag TEXT`: Assign tags to the torrent (can be specified multiple times).
* `--file PATH`: Explicit path to a `.torrent` file.
* `--url TEXT`: Explicit URL to a `.torrent` file.
* `--info-hash TEXT`: Explicit torrent info-hash.

**Examples:**

```shell
# Add from a local file with tags
spritzle add -t linux -t iso archlinux-x86_64.iso.torrent

# Add from a URL
spritzle add https://archlinux.org/releng/releases/latest/torrent/

# Add by info-hash
spritzle add 44a040be6d74d8d290cd20128788864cbf770719
```

### `list` - List Torrents

Displays torrents in a table with customizable fields and filtering.

```shell
spritzle list [OPTIONS]
```

Options:
* `-f, --field TEXT`: Fields to display (can be specified multiple times; default: `name`, `progress`, `download_payload_rate`, `upload_payload_rate`, `state`, `info_hash`).
* `-q, --query TEXT`: Filter query expression in the format `<field>.<op>=<value>` (e.g. `state=seeding`, `progress.ge=0.5`, `spritzle.tags=linux`).
* `-s, --sort TEXT`: Sort results by field name.
* `--header / --no-header`: Toggle table headers.

**Examples:**

```shell
# List all torrents
spritzle list

# Filter torrents by state
spritzle list -q state=downloading

# Display only info-hash and name without table borders
spritzle list -f info_hash -f name --no-header
```

### `remove` - Remove a Torrent

Removes a torrent from the daemon session.

```shell
spritzle remove [OPTIONS] INFO-HASH
```

Options:
* `--delete-files`: Also delete the downloaded payload files from disk.

**Examples:**

```shell
spritzle remove 44a040be6d74d8d290cd20128788864cbf770719
spritzle remove --delete-files 44a040be6d74d8d290cd20128788864cbf770719
```

### `pause` - Pause a Torrent

Pauses downloading and uploading for a torrent.

```shell
spritzle pause INFO-HASH
```

**Example:**

```shell
spritzle pause 44a040be6d74d8d290cd20128788864cbf770719
```

### `resume` - Resume a Torrent

Resumes a previously paused torrent.

```shell
spritzle resume INFO-HASH
```

**Example:**

```shell
spritzle resume 44a040be6d74d8d290cd20128788864cbf770719
```

### `move_storage` - Move Storage Directory

Moves the download files of a torrent to a new filesystem path.

```shell
spritzle move_storage INFO-HASH PATH
```

**Example:**

```shell
spritzle move_storage 44a040be6d74d8d290cd20128788864cbf770719 /mnt/storage/torrents/
```

### `flags` - Inspect and Modify Torrent Flags

Views or modifies libtorrent flags for a specific torrent.

```shell
spritzle flags [OPTIONS] INFO-HASH
```

Options:
* `-s, --sets TEXT`: Enable flag(s) (e.g. `sequential_download`, `super_seeding`, `auto_managed`).
* `-u, --unsets TEXT`: Disable flag(s).
* `--header / --no-header`: Toggle table headers.

**Examples:**

```shell
# View flags
spritzle flags 44a040be6d74d8d290cd20128788864cbf770719

# Set sequential downloading
spritzle flags 44a040be6d74d8d290cd20128788864cbf770719 -s sequential_download
```

### `config` - View and Update Daemon Configuration

Displays or modifies keys in the daemon's SQLite configuration table.

```shell
spritzle config [KEY] [VALUE]
```

**Examples:**

```shell
# Show all configuration
spritzle config

# Get a specific key
spritzle config auth_timeout

# Update a key
spritzle config save_resume_data_interval 30
```

### `settings` - View and Update libtorrent Settings

Inspects or modifies libtorrent session settings.

```shell
spritzle settings [OPTIONS]
```

Options:
* `-s, --sets TEXT`: Setting key/value pair in format `key=value`.
* `--header / --no-header`: Toggle table headers.

**Examples:**

```shell
# View current settings
spritzle settings

# Change max connections
spritzle settings -s connections_limit=200
```

### `stats` - View Session Statistics

Outputs libtorrent session performance metrics (rates, cache statistics, peer counts).

```shell
spritzle stats [OPTIONS]
```

---

## Shell Completion

### Bash Completion Script

Spritzle includes a shell completion script in [`scripts/complete.sh`](../scripts/complete.sh). To enable it in your bash session:

```shell
source /path/to/spritzle/scripts/complete.sh
```

### Click Built-in Completion

You can also use Click's standard completion generation for Bash:

```shell
eval "$(_SPRITZLE_COMPLETE=bash_source spritzle)"
```

Add this line to your `~/.bashrc` to enable automatic completion for `spritzle` commands, options, and info-hashes on every shell login.
