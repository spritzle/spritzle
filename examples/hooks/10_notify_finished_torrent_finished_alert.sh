#!/usr/bin/env bash
#
# Example Hook: 10_notify_finished_torrent_finished_alert.sh
#
# Spritzled invokes matching scripts in ~/.config/spritzle/hooks/ whenever
# a status alert fires. The filename must end in the alert name (e.g. *torrent_finished_alert)
# and must have executable permissions (chmod +x).
#
# Positional Arguments:
#   $1: info_hash (40-char SHA1 hex string)
#   $2: tags (comma-delimited list of tags, e.g. "linux,isos")
#

set -euo pipefail

INFO_HASH="${1:-}"
TAGS="${2:-}"

if [[ -z "${INFO_HASH}" ]]; then
    echo "Error: No info-hash provided" >&2
    exit 1
fi

# Query torrent details using spritzle CLI
NAME=$(spritzle info "${INFO_HASH}" --plain 2>/dev/null | grep -i "^name:" | cut -d: -f2- | xargs || echo "${INFO_HASH}")

# Example: Send a desktop notification using notify-send (if available)
if command -v notify-send >/dev/null 2>&1; then
    notify-send "Spritzle: Download Complete" "Torrent '${NAME}' has finished downloading.\nTags: ${TAGS}"
fi

# Example: Run custom post-processing, move storage, or webhook curl here
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Torrent ${NAME} (${INFO_HASH}) finished with tags: ${TAGS}"
