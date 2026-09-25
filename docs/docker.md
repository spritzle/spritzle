# <img src="assets/logo-icon.svg" alt="Spritzle" width="28" height="28" align="center" /> Running Spritzle in Docker

Spritzle provides an official lightweight container image for `spritzled`, tailored for homelab, NAS, and seedbox environments.

## Features
- **Minimal Footprint**: Multi-stage build based on `python:3.13-slim`.
- **Rootless Operation**: Drops privileges to `spritzle` user (UID/GID configurable via `PUID`/`PGID`).
- **Healthcheck Enabled**: Integrates automatic container health monitoring on `/status`.
- **VPN Leak Prevention**: Native interface binding (`listen_interfaces`) to bind strictly to VPN interfaces (`tun0`, `wg0`).

---

## Quick Start with Docker Compose

Create a `docker-compose.yml`:

```yaml
services:
  spritzled:
    image: spritzle/spritzled:latest
    container_name: spritzled
    restart: unless-stopped
    ports:
      - "17382:17382"       # REST API
      - "6881:6881"         # BitTorrent TCP
      - "6881:6881/udp"     # BitTorrent UDP / DHT
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=UTC
    volumes:
      - ./config:/config
      - ./state:/state
      - ./downloads:/downloads
```

Start the container:
```bash
docker compose up -d
```

---

## VPN Setup with Gluetun

For bulletproof VPN leak protection, pair `spritzled` with [Gluetun](https://github.com/qdm12/gluetun) using Docker's `service` network mode. This routes all container traffic through the VPN and enforces libtorrent interface binding.

Use [`docker-compose.vpn.yml`](../docker-compose.vpn.yml):

```yaml
services:
  vpn:
    image: qmcgaw/gluetun:latest
    container_name: gluetun
    restart: unless-stopped
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    ports:
      - "17382:17382"       # REST API port mapped on VPN container
      - "6881:6881"         # Incoming peer port mapped on VPN container
      - "6881:6881/udp"
    environment:
      - VPN_SERVICE_PROVIDER=custom
      - VPN_TYPE=wireguard
      # Provider-specific WireGuard or OpenVPN settings:
      # - WIREGUARD_PRIVATE_KEY=...
      # - WIREGUARD_ADDRESSES=...
      - FIREWALL_VPN_INPUT_PORTS=6881
    sysctls:
      - net.ipv4.conf.all.src_valid_mark=1

  spritzled:
    image: spritzle/spritzled:latest
    container_name: spritzled
    restart: unless-stopped
    network_mode: "service:vpn"
    depends_on:
      vpn:
        condition: service_healthy
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=UTC
      - VPN_BIND=true
      - LISTEN_INTERFACES=tun0:6881
    volumes:
      - ./config:/config
      - ./state:/state
      - ./downloads:/downloads
```

Run with:
```bash
docker compose -f docker-compose.vpn.yml up -d
```

When `VPN_BIND=true` or `LISTEN_INTERFACES=tun0:6881` is specified:
1. `entrypoint.sh` sets `SPRITZLE_LISTEN_INTERFACES="tun0:6881"`.
2. The daemon initializes libtorrent session settings with `listen_interfaces="tun0:6881"`.
3. If the VPN tunnel drops, BitTorrent packets will never leak onto external interfaces.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PUID` | `1000` | User ID for container file ownership |
| `PGID` | `1000` | Group ID for container file ownership |
| `VPN_BIND` | `false` | When `true`, automatically binds libtorrent to `tun0` or detected VPN interface |
| `LISTEN_INTERFACES` | `""` | Explicit interface binding string (e.g. `tun0:6881`, `wg0:6881`) |
| `SPRITZLE_CONFIG_DIR` | `/config` | Directory where `daemon.toml` is stored |
| `SPRITZLE_STATE_DIR` | `/state` | Directory where resume data, identity, and API keys are stored |
| `SPRITZLE_SAVE_PATH` | `/downloads` | Default torrent download directory |
| `SPRITZLE_PORT` | `17382` | Port for the HTTP REST API |
| `TZ` | `UTC` | Container timezone |

---

## Volume Mounts

- `/config`: Houses `daemon.toml` and CLI client configurations.
- `/state`: Houses `session.state`, `identity`, `keys.json`, and torrent resume data `.resume`.
- `/downloads`: Default storage directory for completed and downloading torrents.
