#!/bin/bash

echo "Getting token.."
TOKEN=$(curl -X POST -d 'password=password' http://localhost:8080/auth | jq -r '.token')

echo "Adding torrent by file.."
curl -i -H "Authorization: ${TOKEN}" -X POST -F "file=@resource/torrents/random_one_file.torrent" -F 'args={"save_path": "/tmp"}' http://localhost:8080/torrent
echo

echo "Adding torrent by URL.."
curl -i -H "Authorization: ${TOKEN}" -X POST -d 'url=https://www.archlinux.org/releng/releases/2017.02.01/torrent/&args={"save_path": "/tmp"}' http://localhost:8080/torrent
echo

echo "Adding torrent by info_hash.."
curl -i -H "Authorization: ${TOKEN}" -X POST -d 'info_hash=88066b90278f2de655ee2dd44e784c340b54e45c&args={"save_path": "/tmp"}' http://localhost:8080/torrent
echo
