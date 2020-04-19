Interface
=========

The main interface to spritzle is REST based. This allows access from almost
any language or environment.

**_Note:_** All examples shown are using [httpie](https://httpie.org), a command line HTTP client, to send requests to spritzle.
This is similar to curl, but allows for much easier interface with JSON REST apis.

Session
-------

The session resource contains information about the libtorrent session.

### /session/settings
#### GET

Returns a dictionary of the session settings.

### /session/stats
#### PUT

Allows changing the session settings. New settings should be JSON format in the
body of request.

### /session/stats
#### GET

Returns a dictionary of the session stats.

**Example**

```shell
$ http GET http://localhost:8080/session/stats
HTTP/1.1 200 OK
Content-Length: 9092
Content-Type: application/json; charset=utf-8
Date: Tue, 08 May 2018 01:03:50 GMT
Server: Python/3.6 aiohttp/3.1.3

{
    "dht.dht_allocated_observers": 10,
    "dht.dht_announce_peer_in": 0,
    "disk.num_blocks_read": 0,
    "disk.num_blocks_written": 0,
    "net.on_tick_counter": 50,
    "net.on_udp_counter": 60,
    "net.sent_tracker_bytes": 0,
    "peer.aborted_peers": 0,
    ...
    "peer.error_utp_peers": 0,
    "peer.incoming_connections": 0,
    "picker.piece_picker_busy_loops": 0,
    "ses.non_filter_torrents": 0,
    "ses.num_checking_torrents": 0,
    "sock_bufs.socket_recv_size10": 0,
    "sock_bufs.socket_recv_size11": 0,
    "utp.num_utp_connected": 0
}
```

### /session/dht
#### GET

Returns a boolean indicating if DHT is running or not.

```shell
$ http GET http://localhost:8080/session/dht
HTTP/1.1 200 OK
Content-Length: 4
Content-Type: application/json; charset=utf-8
Date: Tue, 08 May 2018 01:04:49 GMT
Server: Python/3.6 aiohttp/3.1.3

true
```

Torrent
--------

A torrent resource contains all the information you would need to know about a torrent.

### /torrent
#### GET

Returns a list of all info-hashes in the session, filtered by the query expression.

The query string format is field.operator=expression, where expression is different dependent upon the field's type and operator is the last '.' separated field of the key.

##### Strings
String operations are regular expressions.

**Example**

```shell
$ http GET /torrent?info_hash=^44a04.*$
```

##### Booleans
Booleans are evaluated against two string: 'true', 'false'.

**Example**
```
$ http GET /torrent?boolkey=true
```

##### Numbers
Number expressions can use one of five operators (lt, gt, ne, ge, le), when no operator is presnet in the key an equality operator will be used.

**Example**

```shell
$ http GET /torrent?block_size.ge=0
```

**Example**

```shell
$ http GET http://localhost:8080/torrent
HTTP/1.1 200 OK
Content-Length: 44
Content-Type: application/json; charset=utf-8
Date: Tue, 08 May 2018 01:05:42 GMT
Server: Python/3.6 aiohttp/3.1.3

[
    "44a040be6d74d8d290cd20128788864cbf770719"
]
```

#### POST

Add a torrent to the session. The body of the request should be a JSON encoded dictionary.

There are three ways to add a torrent to the session using one of these three
keys: **file**, **url** or **info_hash**.

Any libtorrent options can also be passed, see
https://libtorrent.org/reference-Core.html#add_torrent_params for reference.

The **spritzle.tags** key can also be passed as a list, containing spritzle tags which should apply to this torrent.

Upon success, you will receive a 201 response and a dictionary with the info_hash in the body. The LOCATION
header will also be set in the response for the new torrent resource.

##### File Upload

Adding a torrent by uploading a torrent file requires the use of a multipart/form-data post with the file contents keyed as **file**.

**Example**

```shell
$ http POST http://localhost:8080/torrent file="$(base64 random_one_file.torrent)" save_path=/tmp
HTTP/1.1 201 Created
Content-Length: 57
Content-Type: application/json; charset=utf-8
Date: Tue, 08 May 2018 01:08:43 GMT
Location: http://localhost:8080/torrent/44a040be6d74d8d290cd20128788864cbf770719
Server: Python/3.6 aiohttp/3.1.3

{
    "info_hash": "44a040be6d74d8d290cd20128788864cbf770719"
}
```

##### URL

Adding a torrent by url is done by setting the **url** key.

**Example**

```shell
$ http POST http://localhost:8080/torrent url=https://www.archlinux.org/releng/releases/2016.02.01/torrent/ save_path=/tmp
HTTP/1.1 201 Created
Content-Length: 57
Content-Type: application/json; charset=utf-8
Date: Tue, 08 May 2018 01:12:01 GMT
Location: http://localhost:8080/torrent/88066b90278f2de655ee2dd44e784c340b54e45c
Server: Python/3.6 aiohttp/3.1.3

{
    "info_hash": "88066b90278f2de655ee2dd44e784c340b54e45c"
}
```

##### Info-hash

Adding a torrent by info-hash is done by setting the **info_hash** key.

**Example**

```shell
$ http POST http://localhost:8080/torrent info_hash=88066b90278f2de655ee2dd44e784c340b54e45c save_path=/tmp
HTTP/1.1 201 Created
Content-Length: 57
Content-Type: application/json; charset=utf-8
Date: Tue, 08 May 2018 01:15:07 GMT
Location: http://localhost:8080/torrent/88066b90278f2de655ee2dd44e784c340b54e45c
Server: Python/3.6 aiohttp/3.1.3

{
    "info_hash": "88066b90278f2de655ee2dd44e784c340b54e45c"
}
```

#### DELETE

Remove all torrents from the session.

Optionally, the downloaded files can be deleted when the torrent is removed by adding
the **delete_files** key to the query string.

**Example**
```shell
$ http DELETE http://localhost:8080/torrent?delete_files
HTTP/1.1 200 OK
Content-Length: 0
Content-Type: application/octet-stream
Date: Tue, 08 May 2018 01:16:03 GMT
Server: Python/3.6 aiohttp/3.1.3
```

### /torrent/\<info-hash\>
#### GET

Returns a status dictionary for the torrent.

**Example**

```shell
$ http GET http://localhost:8080/torrent/44a040be6d74d8d290cd20128788864cbf770719
HTTP/1.1 200 OK
Content-Length: 4059
Content-Type: application/json; charset=utf-8
Date: Tue, 08 May 2018 01:18:07 GMT
Server: Python/3.6 aiohttp/3.1.3

{
    "auto_managed": false,
    "download_payload_rate": 0,
    "download_rate": 0,
    "has_incoming": false,
    "has_metadata": true,
    "info_hash": "44a040be6d74d8d290cd20128788864cbf770719",
    ...
    "total_redundant_bytes": 0,
    "total_upload": 0,
    "total_wanted": 4194304,
    "upload_rate": 0,
    "uploads_limit": -1,
    "verified_pieces": []
}
```

#### DELETE

Remove torrent from the session.

Optionally, the downloaded files can be deleted when the torrent is removed by adding
the **delete_files** key to the query string.

**Example**

```shell
$ http DELETE http://localhost:8080/torrent/88066b90278f2de655ee2dd44e784c340b54e45c?delete_files
HTTP/1.1 200 OK
Content-Length: 0
Content-Type: application/octet-stream
Date: Tue, 08 May 2018 01:12:36 GMT
Server: Python/3.6 aiohttp/3.1.3
```

### /torrent/<info-hash>/flags

#### GET
                                    
Returns a (string, bool) dictionary of the torrent flags.

**Example**

```shell
$ http GET http://localhost:8080/torrent/0175df556a2123361a55c1f72ad1aa73d03d7830/flags Authorization:$TOKEN
HTTP/1.1 200 OK
Content-Length: 320
Content-Type: application/json; charset=utf-8
Date: Thu, 14 Feb 2019 05:30:52 GMT
Server: Python/3.7 aiohttp/3.5.4

{
    "apply_ip_filter": true,
    "auto_managed": true,
    "duplicate_is_error": false,
    "override_trackers": false,
    "override_web_seeds": false,
    "paused": false,
    "seed_mode": false,
    "sequential_download": false,
    "share_mode": false,
    "stop_when_ready": false,
    "super_seeding": false,
    "update_subscribe": false,
    "upload_mode": false
}
```
#### PUT

Change the flags by passing in a dictionary (string, bool).

**Example**

```shell
$ http PUT http://localhost:8080/torrent/0175df556a2123361a55c1f72ad1aa73d03d7830/flags Authorization:$TOKEN auto_managed:=false share_mode:=true

HTTP/1.1 200 OK
Content-Length: 320
Content-Type: application/json; charset=utf-8
Date: Thu, 14 Feb 2019 06:03:57 GMT
Server: Python/3.7 aiohttp/3.5.4

{
    "apply_ip_filter": true,
    "auto_managed": false,
    "duplicate_is_error": false,
    "override_trackers": false,
    "override_web_seeds": false,
    "paused": false,
    "seed_mode": false,
    "sequential_download": false,
    "share_mode": true,
    "stop_when_ready": false,
    "super_seeding": false,
    "update_subscribe": false,
    "upload_mode": false
}
```

Core
----
### /core
#### DELETE

Initiates Spritzle shutdown.

**Example**

```shell
$ http DELETE http://localhost:8080/core
HTTP/1.1 200 OK
Content-Length: 0
Content-Type: application/octet-stream
Date: Tue, 08 May 2018 01:21:31 GMT
Server: Python/3.6 aiohttp/3.1.3
```
