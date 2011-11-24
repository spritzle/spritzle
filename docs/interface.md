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

A torrent resource contains all the information you would need to know about a torrent.

```javascript
{
 // Torrent status keys
 "queue",
 "name",
 "total_size",
 "state",
 "progress",
 "num_seeds",
 "total_seeds",
 "num_peers",
 "total_peers",
 "download_payload_rate",
 "upload_payload_rate",
 "eta",
 "ratio",
 "distributed_copies",
 "time_added",
 "tracker_host",
 "save_path",
 "last_seen_complete",
 "owner",
 "public",
 "shared",
 "total_done",
 "total_payload_download",
 "total_uploaded",
 "total_payload_upload",
 "next_announce",
 "tracker_status",
 "num_pieces",
 "piece_length",
 "active_time",
 "seeding_time",
 "seed_rank",
 "peers",
 "num_files",
 "message",
 "tracker",
 "comment",
 
 // Torrent configuration options
 "max_download_speed",
 "max_upload_speed",
 "max_connections",
 "max_upload_slots",
 "is_auto_managed",
 "stop_at_ratio",
 "stop_ratio",
 "remove_at_ratio",
 "private",
 "prioritize_first_last",
 "move_completed",
 "move_completed_path"
}
```

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