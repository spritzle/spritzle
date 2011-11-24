Interface
=========

The main interface to spritzle is REST based. This allows access from almost
any language or environment.

Authentication
--------------
- POST /auth            - Login to the server

Torrents
--------
- GET  /torrent         - List all torrents
- GET  /torrent/\<hash\>  - List a torrent
- PUT  /torrent/\<hash\>  - Update a torrent
- POST /torrent         - Create a new torrent
