Interface
=========

The main interface to spritzle is REST based. This allows access from almost
any language or environment.

**_Note:_** All examples shown are using [httpie](https://httpie.org), a command line HTTP client, to send requests to spritzle.
This is similar to curl, but allows for much easier interface with JSON REST apis.

Authentication & Status
-----------------------

All endpoints require authentication using a valid API key with prefix `spritzle_`.
API keys can be supplied via either:
- HTTP Header: `Authorization: Bearer <api_key>`
- HTTP Header: `X-API-Key: <api_key>`

Upon successful authentication, `spritzled` attaches its persistent daemon instance identifier in the `X-Spritzle-Daemon-Id` response header. Unauthenticated or invalid requests receive `HTTP 401 Unauthorized` and do not leak daemon identity or version details.

### /status
#### GET

Returns status, persistent daemon identifier, software version, uptime (in seconds), and active torrent count. Requires authentication.

**Example**

```shell
$ http GET http://localhost:17382/status "Authorization: Bearer spritzle_8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c"
HTTP/1.1 200 OK
Content-Length: 120
Content-Type: application/json; charset=utf-8
X-Spritzle-Daemon-Id: spz_d_4a9e2f80c1

{
    "daemon_id": "spz_d_4a9e2f80c1",
    "num_torrents": 5,
    "status": "ok",
    "uptime": 8123.4,
    "version": "1.0.0"
}
```

### /keys
#### GET
List all API keys (active and revoked).

#### POST
Create a new API key. Accepts optional `{"name": "client_name"}` JSON payload. Returns the raw API key (only displayed once upon creation).

### /keys/{id}
#### DELETE
Revoke an existing API key by its unique ID.


Error Responses
---------------

Spritzle daemons return structured JSON error responses with standard HTTP status codes:

```json
{
    "status": 400,
    "reason": "Bad Request",
    "message": "Invalid info-hash format: 123"
}
```

Common status codes:
* `200 OK`: Request succeeded.
* `201 Created`: Resource successfully created (e.g. `POST /torrent`, `POST /keys`).
* `400 Bad Request`: Malformed JSON, invalid query parameter, unknown flag, or unsupported torrent method.
* `401 Unauthorized`: Missing, invalid, or revoked API key.
* `404 Not Found`: Torrent or API key not found.
* `500 Internal Server Error`: Unexpected daemon error.


Daemon Configuration
--------------------

Manage daemon settings stored in `daemon.toml`.

### /config
#### GET

Returns the current daemon configuration dictionary.

**Example**

```shell
$ http GET http://localhost:17382/config "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

{
    "add_torrent_params.save_path": "/home/user/Downloads",
    "save_resume_data_interval": 60
}
```

#### PUT

Replaces all configuration settings with the provided JSON object.

**Example**

```shell
$ http PUT http://localhost:17382/config "Authorization: Bearer $TOKEN" save_resume_data_interval:=30
HTTP/1.1 200 OK
```

#### PATCH

Partially updates specified keys in the daemon configuration.

**Example**

```shell
$ http PATCH http://localhost:17382/config "Authorization: Bearer $TOKEN" add_torrent_params.save_path="/mnt/storage/downloads"
HTTP/1.1 200 OK
```


Session
-------

The session resource contains information about the libtorrent session.

### /session/settings
#### GET

Returns a dictionary of the current libtorrent session settings.

**Query Parameters:**
* `modified=true`: Return only settings that differ from libtorrent baseline default values.

**Example**

```shell
$ http GET http://localhost:17382/session/settings?modified=true "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

{
    "download_rate_limit": 1048576,
    "user_agent": "Spritzle/1.0 libtorrent/2.0.11"
}
```

#### PUT

Updates one or more session settings. The request body must be a JSON object mapping setting names to values.

**Example**

```shell
$ http PUT http://localhost:17382/session/settings "Authorization: Bearer $TOKEN" connections_limit:=200 download_rate_limit:=1048576
HTTP/1.1 200 OK
```

### /session/settings/defaults
#### GET

Returns the factory baseline defaults for all libtorrent session settings.

**Example**

```shell
$ http GET http://localhost:17382/session/settings/defaults "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
```

### /session/settings/reset
#### POST

Resets specified session settings or all session settings back to baseline defaults.

**Payload:**
* `{"keys": ["setting1", "setting2"]}`: Reset specified settings.
* `{"all": true}`: Reset all settings to baseline defaults.

**Example**

```shell
$ http POST http://localhost:17382/session/settings/reset "Authorization: Bearer $TOKEN" keys:='["download_rate_limit"]'
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

{
    "reset": [
        "download_rate_limit"
    ]
}
```

### /session/stats
#### GET

Returns a dictionary of the session stats.

**Example**

```shell
$ http GET http://localhost:17382/session/stats "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
Content-Length: 9092
Content-Type: application/json; charset=utf-8

{
    "dht.dht_allocated_observers": 10,
    "dht.dht_announce_peer_in": 0,
    "disk.num_blocks_read": 0,
    "disk.num_blocks_written": 0,
    "net.on_tick_counter": 50,
    "net.on_udp_counter": 60,
    "net.sent_tracker_bytes": 0,
    "peer.aborted_peers": 0,
    "picker.piece_picker_busy_loops": 0,
    "utp.num_utp_connected": 0
}
```

### /session/dht
#### GET

Returns a boolean indicating if DHT is running or not.

```shell
$ http GET http://localhost:17382/session/dht "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
Content-Length: 4
Content-Type: application/json; charset=utf-8

true
```

Torrent
--------

A torrent resource contains all the information you would need to know about a torrent.

### /torrent
#### GET

Returns a list of all info-hashes in the session, filtered by the query expression.

The query string format is `<field>[.(op)]=<expression>`, where `<op>` is the operator and `<expression>` depends on the field's type.

##### Strings
String queries support regex matching (`eq` or omitted operator) and regex non-matching (`ne`).

**Examples:**
```shell
$ http GET http://localhost:17382/torrent?name=^archlinux.*$
$ http GET http://localhost:17382/torrent?state.ne=seeding
```

##### Booleans
Booleans evaluate against `"true"` and `"false"`. Supports `eq` (or omitted) and `ne`.

**Examples:**
```shell
$ http GET http://localhost:17382/torrent?paused=true
$ http GET http://localhost:17382/torrent?auto_managed.ne=true
```

##### Numbers
Number expressions support comparison operators: `eq` (or omitted), `lt`, `gt`, `ne`, `ge`, `le`.

**Examples:**
```shell
$ http GET http://localhost:17382/torrent?progress.ge=0.5
$ http GET http://localhost:17382/torrent?download_rate.gt=102400
```

##### Lists (Tags)
For list fields such as `spritzle.tags`, four operators are supported:
* `any` (or omitted): Regex match against any item in the list.
* `all`: Matches if all comma-separated items are present in the list (`spritzle.tags.all=linux,iso`).
* `in`: Matches if any item in the torrent's list is present in the comma-separated target list (`spritzle.tags.in=linux,distro`).

**Examples:**
```shell
$ http GET http://localhost:17382/torrent?spritzle.tags=linux
$ http GET http://localhost:17382/torrent?spritzle.tags.all=linux,iso
```

**Example Response:**

```shell
$ http GET http://localhost:17382/torrent "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
Content-Length: 44
Content-Type: application/json; charset=utf-8

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
$ http POST http://localhost:17382/torrent "Authorization: Bearer $TOKEN" file="$(base64 random_one_file.torrent)" save_path=/tmp
HTTP/1.1 201 Created
Content-Length: 57
Content-Type: application/json; charset=utf-8
Location: http://localhost:17382/torrent/44a040be6d74d8d290cd20128788864cbf770719

{
    "info_hash": "44a040be6d74d8d290cd20128788864cbf770719"
}
```

##### URL

Adding a torrent by url is done by setting the **url** key.

**Example**

```shell
$ http POST http://localhost:17382/torrent "Authorization: Bearer $TOKEN" url=https://archlinux.org/releng/releases/latest/torrent/ save_path=/tmp
HTTP/1.1 201 Created
Content-Length: 57
Content-Type: application/json; charset=utf-8
Location: http://localhost:17382/torrent/88066b90278f2de655ee2dd44e784c340b54e45c

{
    "info_hash": "88066b90278f2de655ee2dd44e784c340b54e45c"
}
```

##### Info-hash

Adding a torrent by info-hash is done by setting the **info_hash** key.

**Example**

```shell
$ http POST http://localhost:17382/torrent "Authorization: Bearer $TOKEN" info_hash=88066b90278f2de655ee2dd44e784c340b54e45c save_path=/tmp
HTTP/1.1 201 Created
Content-Length: 57
Content-Type: application/json; charset=utf-8
Location: http://localhost:17382/torrent/88066b90278f2de655ee2dd44e784c340b54e45c

{
    "info_hash": "88066b90278f2de655ee2dd44e784c340b54e45c"
}
```

#### DELETE

Remove torrents from the session. If query parameters are provided (e.g. `state=seeding`), only torrents matching the query expression are removed; otherwise, all torrents in the session are removed.

Optionally, downloaded files can be deleted when the torrent is removed by adding
the `delete_files` parameter to the query string.

**Examples:**
```shell
# Remove all torrents and delete their downloaded files
$ http DELETE "http://localhost:17382/torrent?delete_files" "Authorization: Bearer $TOKEN"

# Remove only finished torrents
$ http DELETE "http://localhost:17382/torrent?progress.ge=1.0" "Authorization: Bearer $TOKEN"
```

### /torrent/\<info-hash\>
#### GET

Returns a status dictionary for the torrent.

**Example**

```shell
$ http GET http://localhost:17382/torrent/44a040be6d74d8d290cd20128788864cbf770719 "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
Content-Length: 4059
Content-Type: application/json; charset=utf-8

{
    "auto_managed": false,
    "download_payload_rate": 0,
    "download_rate": 0,
    "has_incoming": false,
    "has_metadata": true,
    "info_hash": "44a040be6d74d8d290cd20128788864cbf770719",
    "name": "archlinux-x86_64.iso",
    "progress": 0.42,
    "total_size": 1234567890
}
```

#### DELETE

Remove torrent from the session.

Optionally, the downloaded files can be deleted when the torrent is removed by adding
the `delete_files` parameter to the query string.

**Example**

```shell
$ http DELETE "http://localhost:17382/torrent/44a040be6d74d8d290cd20128788864cbf770719?delete_files" "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
Content-Length: 0
```

### /torrent/\<info-hash\>/flags

#### GET
                                    
Returns a `{"<flag_name>": bool}` dictionary of torrent flags.

**Example**

```shell
$ http GET http://localhost:17382/torrent/44a040be6d74d8d290cd20128788864cbf770719/flags "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

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

Update multiple flags at once by passing a JSON object mapping flag names to booleans.

**Example**

```shell
$ http PUT http://localhost:17382/torrent/44a040be6d74d8d290cd20128788864cbf770719/flags "Authorization: Bearer $TOKEN" auto_managed:=false sequential_download:=true
HTTP/1.1 200 OK
```

### /torrent/\<info-hash\>/flags/\<flag\>

#### GET

Returns the boolean status of a single flag.

**Example**

```shell
$ http GET http://localhost:17382/torrent/44a040be6d74d8d290cd20128788864cbf770719/flags/sequential_download "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK

true
```

#### PUT

Sets the boolean value for a single flag. The body should be a boolean JSON literal or `{"value": true/false}`.

**Example**

```shell
$ http PUT http://localhost:17382/torrent/44a040be6d74d8d290cd20128788864cbf770719/flags/sequential_download "Authorization: Bearer $TOKEN" value:=true
HTTP/1.1 200 OK
```

### /torrent/\<info-hash\>/\<method\>

#### POST

Invokes an allowed libtorrent handle operation on the torrent. The request body must be a JSON array of arguments (or empty array `[]` if the method takes no arguments).

**Allowed Methods:**
* `pause`: Pauses the torrent.
* `resume`: Resumes the torrent.
* `force_recheck`: Forces piece hash verification.
* `force_reannounce`: Forces tracker reannouncement.
* `force_dht_announce`: Forces DHT announce.
* `queue_position_up` / `queue_position_down` / `queue_position_top` / `queue_position_bottom`: Adjusts queue position.
* `set_max_uploads`: Sets upload slot limit (argument: `[limit]`).
* `set_upload_limit`: Sets upload rate limit in bytes/second (argument: `[bytes_per_sec]`).
* `set_download_limit`: Sets download rate limit in bytes/second (argument: `[bytes_per_sec]`).
* `set_max_connections`: Sets max connection count (argument: `[limit]`).
* `set_sequential_download`: Enables or disables sequential downloading (argument: `[true|false]`).
* `clear_error`: Clears error state on the torrent.
* `flush_cache`: Flushes the torrent disk cache.
* `move_storage`: Moves storage directory to a new path (argument: `["/new/path"]`).

**Examples:**

```shell
# Pause a torrent
$ http POST http://localhost:17382/torrent/44a040be6d74d8d290cd20128788864cbf770719/pause "Authorization: Bearer $TOKEN"

# Move storage directory
$ echo '["/mnt/storage/downloads"]' | http POST http://localhost:17382/torrent/44a040be6d74d8d290cd20128788864cbf770719/move_storage "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
```

Core
----
### /core
#### DELETE

Initiates graceful Spritzle shutdown. Flushes resume data, saves libtorrent session state, and cleanly terminates the daemon.

**Example**

```shell
$ http DELETE http://localhost:17382/core "Authorization: Bearer $TOKEN"
HTTP/1.1 200 OK
Content-Length: 0
```
