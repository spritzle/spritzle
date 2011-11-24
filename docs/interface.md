Interface
=========

The main interface to spritzle is REST based. This allows access from almost
any language or environment.

Authentication
--------------
- /auth
 - POST: Login to the server

Torrents
--------
- /torrent
 - GET: List all torrents
 - POST: Create a new torrent
- /torrent/\<hash\> 
 - GET: Fetch a torrents details
 - PUT: Update a torrent
 - DELETE: Remove a torrent