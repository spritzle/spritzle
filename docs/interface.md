Interface
=========

The main interface to spritzle is REST based. This allows access from almost
any language or environment.

POST /auth            - Login to the server

GET  /torrent         - List all torrents
GET  /torrent/<hash>  - List a torrent
PUT  /torrent/<hash>  - Update a torrent
POST /torrent         - Create a new torrent
