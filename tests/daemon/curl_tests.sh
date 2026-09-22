#!/bin/bash

echo "Getting token.."
TOKEN=$(curl -X POST -d '{"password": "password"}' http://localhost:8080/auth | jq -r '.token')

echo "Adding torrent by file.."
curl -i -H "Authorization: ${TOKEN}" -X POST -F "file=@resource/torrents/random_one_file.torrent" -F 'args={"save_path": "/tmp"}' http://localhost:8080/torrent
echo

echo "Adding torrent by URL.."
curl -i -H "Authorization: ${TOKEN}" -X POST -d 'url=http://localhost:8080/test_torrents/random_one_file.torrent&args={"save_path": "/tmp"}' http://localhost:8080/torrent
echo

echo "Adding torrent by info_hash.."
curl -i -H "Authorization: ${TOKEN}" -X POST -d 'info_hash=44a040be6d74d8d290cd20128788864cbf770719&args={"save_path": "/tmp"}' http://localhost:8080/torrent
echo
