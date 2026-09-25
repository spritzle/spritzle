#!/usr/bin/env bash
set -euo pipefail

KEY="${1:-}"
PORT="${2:-17382}"

if [ -z "${KEY}" ]; then
    echo "Usage: $0 <api-key> [port]"
    echo "Example: $0 spritzle_... 17382"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Adding torrent by file..."
curl -i -H "X-Api-Key: ${KEY}" -X POST -F "file=@${SCRIPT_DIR}/torrents/random_one_file.torrent" -F 'args={"save_path": "/tmp"}' "http://localhost:${PORT}/torrent"
echo

echo "Adding torrent by URL..."
curl -i -H "X-Api-Key: ${KEY}" -X POST -d "url=http://localhost:${PORT}/test_torrents/random_one_file.torrent&args={\"save_path\": \"/tmp\"}" "http://localhost:${PORT}/torrent"
echo

echo "Adding torrent by info_hash..."
curl -i -H "X-Api-Key: ${KEY}" -X POST -d 'info_hash=44a040be6d74d8d290cd20128788864cbf770719&args={"save_path": "/tmp"}' "http://localhost:${PORT}/torrent"
echo
