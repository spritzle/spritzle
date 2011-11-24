Interface
=========

The main interface to spritzle is REST based. This allows access from almost
any language or environment.

Authentication
--------------
- /auth
 - GET: Fetch session information
 - POST: Login to the server
 - DELETE: Logout of the server

Configuration
-------------
- /config
 - GET: Get the global configuration
 - PUT: Update the global configuration

Session
-------
- /session
 - GET: Fetch the libtorrent session status
 - PUT: Update the libtorrent session options

Torrents
--------
- /torrent
 - GET: List all torrents
 - POST: Create a new torrent
- /torrent/\<hash\> 
 - GET: Fetch a torrents details
 - PUT: Update a torrent
 - DELETE: Remove a torrent

User
----
- /user
 - GET: Return a list of the users
 - POST: Create a new user
- /user/\<id\>
 - GET: Fetch a users details
 - PUT: Update a users information
 - DELETE: Remove the user