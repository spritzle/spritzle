# Managing Remote Daemons & API Keys

Spritzle CLI supports managing multiple remote or local daemon instances through named **remotes**. Each remote associates a friendly name with a daemon URL, an API key, and the daemon's persistent instance identity.

---

## 1. Overview & Architecture

### API Key Authentication
All authenticated operations in Spritzle use high-entropy API keys (formatted as `spritzle_<32 hex chars>`). On the daemon, keys are stored solely as SHA-256 hashes in `~/.local/share/spritzle/state/keys.json`, enabling immediate individual revocation.

### Daemon Identity Protection
Every `spritzled` daemon automatically generates a unique, persistent **Daemon ID** (`daemon_id`) stored in its state directory (e.g. `spz_d_4a9e2f80c1`).

When you add a remote to `spritzle-cli`, the client probes the daemon, verifies its identity, and records the `daemon_id`. Before dispatching commands or sending API keys to a remote daemon, the CLI validates that the target daemon's identity matches the stored fingerprint. If a remote IP or port is reassigned to another service, the CLI refuses to transmit your API key, preventing credential leakage.

---

## 2. Zero-Config Local Client Discovery

When `spritzled` runs locally, it automatically generates an API key for the local client and writes a discovery file to:
```
~/.local/share/spritzle/state/local_remote.json  (permissions 0600)
```
On its first run, `spritzle-cli` automatically reads this discovery file and configures a `local` remote as the default. Local commands (`spritzle list`, `spritzle stats`) work immediately out of the box without requiring manual authentication or key importing.

---

## 3. Managing Remotes with `spritzle remote`

All remote daemon connections and key imports are managed using the `spritzle remote` command family.

### Adding a Remote (`remote add`)

To configure a new remote daemon, supply a name, the daemon URL, and the API key:

```shell
# Add remote with explicit key
spritzle remote add seedbox https://seedbox.example.com:8080 --key spritzle_8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c

# Or omit --key to be prompted securely
spritzle remote add seedbox https://seedbox.example.com:8080
API Key for 'seedbox': 
```

During `remote add`, the CLI:
1. Authenticates against `<url>/status` with the provided API key to verify connectivity, validate the key, and retrieve the daemon's `daemon_id`.
2. Persists the remote configuration to `~/.config/spritzle/remotes.toml` (file mode `0600`).
3. If no default remote has been configured, automatically marks this new remote as default.

If the remote already exists, use `--force` or `remote set-key` to update it:
```shell
spritzle remote add seedbox https://seedbox.example.com:8080 --key spritzle_newkey --force
```

### Checking Daemon Status & Latency (`remote status`)

To check the connectivity, latency, version, uptime, and torrent count across all configured remotes or for a specific remote:

```shell
# Check status of all configured remotes concurrently
spritzle remote status

# Check status of a single remote
spritzle remote status seedbox
```

Output:
```
  Name     Status   Latency  URL                              Version  Uptime     Torrents
* local    online      2 ms  http://127.0.0.1:8080            1.0.0    2h 15m            3
  seedbox  online     42 ms  https://seedbox.example.com:8080 1.0.0    14d 6h           48
```

Possible status states:
- `online`: Daemon reachable, authenticated successfully, identity verified.
- `auth_failed`: Daemon reached but returned HTTP 401 Unauthorized (invalid/revoked API key).
- `id_mismatch`: Daemon reached but responded with a different `daemon_id` than recorded during `remote add`.
- `offline`: Daemon could not be contacted (network error, timeout, or port closed).

Machine-readable output formats are supported:
```shell
spritzle remote status --plain
spritzle remote status --json
spritzle remote status seedbox --json
```

### Updating an API Key (`remote set-key`)

To update or import a new API key for an existing remote:

```shell
spritzle remote set-key seedbox spritzle_newkey123...

# Or without passing the key on the command line:
spritzle remote set-key seedbox
New API Key for 'seedbox': 
```

### Listing Remotes (`remote list`)

List all configured remotes, their endpoints, daemon IDs, and default indicator:

```shell
spritzle remote list
```

Output:
```
  Name     URL                              Daemon ID
* local    http://127.0.0.1:8080            spz_d_1a2b3c4d
  seedbox  https://seedbox.example.com:8080 spz_d_4a9e2f80
```

Machine-readable output formats are supported:
```shell
spritzle remote list --plain
spritzle remote list --json
```

### Switching the Default Remote (`remote use`)

To set the default remote for all subsequent commands:

```shell
spritzle remote use seedbox
```

### Inspecting Remote Details (`remote show`)

View detailed information for a remote (API keys are masked for security):

```shell
spritzle remote show seedbox
```

### Removing a Remote (`remote remove`)

To remove a configured remote:

```shell
spritzle remote remove seedbox
```

---

## 4. Targeting Remotes in Commands

You can direct any `spritzle` command to a specific remote without changing your default configuration:

```shell
# Use a specific remote for a single command
spritzle -r seedbox list
spritzle --remote seedbox stats

# Or set the SPRITZLE_REMOTE environment variable
export SPRITZLE_REMOTE=seedbox
spritzle list
```

---

## 5. Generating & Revoking Keys on the Daemon

On the host running `spritzled`, keys are managed via `spritzled key`:

```shell
# Generate an API key for a third-party client (e.g. Sonarr, laptop)
spritzled key create --name "sonarr"

# List active and revoked keys
spritzled key list

# Instantly revoke a key by ID or name
spritzled key revoke "sonarr"
```
