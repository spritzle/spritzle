#!/bin/sh
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Auto-detect or enforce VPN interface binding if requested
if [ "$VPN_BIND" = "true" ] || [ "$VPN_BIND" = "1" ]; then
    if [ -z "$LISTEN_INTERFACES" ]; then
        # Search for tun or wg interface
        DETECTED_IFACE=$(ip -o link show 2>/dev/null | awk -F': ' '{print $2}' | grep -E '^(tun|wg)[0-9]+' | head -n 1 || true)
        if [ -n "$DETECTED_IFACE" ]; then
            echo "[entrypoint] VPN_BIND enabled: Detected VPN interface '$DETECTED_IFACE'. Binding BitTorrent listen_interfaces to ${DETECTED_IFACE}:6881."
            export SPRITZLE_LISTEN_INTERFACES="${DETECTED_IFACE}:6881"
        else
            echo "[entrypoint] WARNING: VPN_BIND=true was specified, but no tun/wg interface was detected yet. Defaulting to tun0:6881."
            export SPRITZLE_LISTEN_INTERFACES="tun0:6881"
        fi
    fi
fi

if [ -n "$LISTEN_INTERFACES" ]; then
    export SPRITZLE_LISTEN_INTERFACES="$LISTEN_INTERFACES"
fi

# If running as root, configure PUID/PGID and drop privileges via gosu
if [ "$(id -u)" = "0" ]; then
    # Ensure spritzle group has the correct GID
    if [ "$PGID" != "$(id -g spritzle 2>/dev/null)" ]; then
        groupmod -o -g "$PGID" spritzle 2>/dev/null || true
    fi

    # Ensure spritzle user has the correct UID
    if [ "$PUID" != "$(id -u spritzle 2>/dev/null)" ]; then
        usermod -o -u "$PUID" spritzle 2>/dev/null || true
    fi

    # Ensure required directories exist and are owned by spritzle
    mkdir -p /config /state /downloads
    chown -R spritzle:spritzle /config /state
    # Only chown /downloads root directory, avoid deep traversal on large existing libraries
    chown spritzle:spritzle /downloads

    exec gosu spritzle "$@"
else
    exec "$@"
fi
