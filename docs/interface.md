Interface
=========

The main interface to spritzle is REST based. This allows access from almost
any language or environment.

Session
-------

The session resource contains information about the libtorrent session.

### /session
#### GET

Returns a dictionary of the session status.

**Example**

```shell
$ curl -i -X GET http://localhost:8080/session
HTTP/1.1 200 OK
CONTENT-TYPE: application/json; charset=utf-8
CONTENT-LENGTH: 8997
DATE: Thu, 18 Feb 2016 02:48:33 GMT
SERVER: Python/3.5 aiohttp/0.21.0

{"disk.queued_write_bytes": 0, "peer.timeout_peers": 0, "disk.num_fenced_write": 0, "picker.end_game_piece_picks": 0, "disk.arc_mru_ghost_size": 0, "net.on_tick_counter": 162784, "ses.num_incoming_ext_handshake": 0, "ses.num_outgoing_have": 0, "net.on_lsd_peer_counter": 0, "disk.num_fenced_flush_piece": 0, "dht.dht_immutable_data": 0, "peer.no_memory_peers": 0, "dht.dht_find_node_in": 0, "sock_bufs.socket_recv_size12": 0, "ses.num_incoming_allowed_fast": 0, "ses.num_downloading_torrents": 1, "utp.utp_samples_above_target": 0, "sock_bufs.socket_recv_size5": 0, "net.sent_tracker_bytes": 0, "sock_bufs.socket_send_size5": 0, "dht.dht_get_peers_in": 0, "disk.arc_write_size": 0, "peer.choked_piece_requests": 0, "sock_bufs.socket_recv_size4": 0, "peer.num_peers_up_interested": 0, "peer.connect_timeouts": 0, "dht.dht_find_node_out": 0, "picker.reject_piece_picks": 0, "peer.aborted_peers": 0, "disk.num_jobs": 0, "peer.num_ssl_peers": 0, "ses.num_error_torrents": 0, "peer.invalid_arg_peers": 0, "net.limiter_down_bytes": 0, "ses.num_incoming_cancel": 0, "ses.num_incoming_have_none": 0, "picker.piece_picker_reverse_rare_loops": 0, "utp.utp_packet_loss": 0, "ses.num_outgoing_suggest": 0, "sock_bufs.socket_recv_size7": 0, "disk.read_cache_blocks": 0, "net.on_write_counter": 0, "ses.num_outgoing_request": 0, "net.recv_bytes": 0, "disk.num_blocks_cache_hits": 0, "disk.disk_blocks_in_use": 0, "utp.num_utp_deleted": 0, "net.recv_redundant_bytes": 0, "net.recv_ip_overhead_bytes": 0, "disk.num_read_ops": 0, "peer.max_piece_requests": 0, "disk.num_fenced_file_priority": 0, "net.on_lsd_counter": 271, "ses.waste_piece_cancelled": 0, "peer.piece_requests": 0, "ses.num_seeding_torrents": 0, "utp.num_utp_syn_sent": 0, "peer.invalid_piece_requests": 0, "peer.error_tcp_peers": 0, "peer.num_peers_up_requests": 0, "disk.num_running_threads": 4, "peer.error_peers": 0, "dht.dht_bytes_out": 0, "ses.num_outgoing_choke": 0, "utp.utp_timeout": 0, "net.on_udp_counter": 0, "sock_bufs.socket_send_size18": 0, "ses.num_checking_torrents": 0, "picker.piece_picker_busy_loops": 0, "disk.num_blocks_hashed": 0, "disk.num_write_ops": 0, "peer.num_utp_peers": 0, "peer.too_many_peers": 0, "peer.num_peers_down_requests": 0, "dht.dht_invalid_put": 0, "ses.num_outgoing_piece": 0, "dht.dht_mutable_data": 0, "dht.dht_nodes": 0, "net.sent_payload_bytes": 0, "peer.broken_pipe_peers": 0, "picker.piece_picker_sequential_loops": 0, "dht.dht_get_in": 0, "peer.num_peers_up_unchoked_all": 0, "peer.num_peers_connected": 0, "sock_bufs.socket_send_size19": 0, "peer.num_tcp_peers": 0, "picker.interesting_piece_picks": 0, "peer.num_peers_up_unchoked": 0, "utp.utp_fast_retransmit": 0, "ses.num_outgoing_ext_handshake": 0, "utp.utp_payload_pkts_in": 0, "dht.dht_ping_in": 0, "ses.num_piece_failed": 0, "disk.num_fenced_flush_storage": 0, "disk.num_blocks_written": 0, "sock_bufs.socket_send_size13": 0, "peer.num_peers_down_interested": 0, "disk.num_fenced_check_fastresume": 0, "utp.utp_redundant_pkts_in": 0, "disk.num_fenced_stop_torrent": 0, "ses.waste_piece_end_game": 0, "peer.addrinuse_peers": 0, "dht.dht_messages_in": 0, "net.recv_tracker_bytes": 0, "disk.num_fenced_save_resume_data": 0, "sock_bufs.socket_send_size12": 0, "sock_bufs.socket_send_size20": 0, "peer.num_peers_half_open": 0, "ses.num_incoming_unchoke": 0, "net.limiter_up_queue": 0, "sock_bufs.socket_send_size17": 0, "net.limiter_up_bytes": 0, "ses.num_outgoing_have_none": 0, "peer.num_peers_up_unchoked_optimistic": 0, "ses.num_outgoing_interested": 0, "picker.piece_picker_partial_loops": 0, "ses.waste_piece_unknown": 0, "disk.num_fenced_release_files": 0, "dht.dht_invalid_get": 0, "utp.utp_invalid_pkts_in": 0, "picker.incoming_redundant_piece_picks": 0, "picker.piece_picker_rand_start_loops": 0, "disk.pinned_blocks": 0, "peer.num_peers_end_game": 0, "ses.num_outgoing_dht_port": 0, "peer.num_ssl_http_proxy_peers": 0, "dht.dht_bytes_in": 0, "disk.num_fenced_load_torrent": 0, "peer.disconnected_peers": 0, "peer.num_http_proxy_peers": 0, "ses.num_unchoke_slots": 8, "disk.num_fenced_trim_cache": 0, "ses.num_incoming_not_interested": 0, "dht.dht_torrents": 0, "ses.num_outgoing_bitfield": 0, "dht.dht_peers": 0, "peer.error_encrypted_peers": 0, "peer.perm_peers": 0, "picker.unchoke_piece_picks": 0, "ses.num_outgoing_cancel": 0, "ses.num_upload_only_torrents": 0, "ses.torrent_evicted_counter": 0, "disk.num_fenced_cache_piece": 0, "ses.waste_piece_seed": 0, "net.sent_ip_overhead_bytes": 0, "ses.num_incoming_pex": 0, "net.on_disk_counter": 1, "disk.num_writing_threads": 0, "disk.num_running_disk_jobs": 0, "ses.num_outgoing_extended": 0, "sock_bufs.socket_recv_size10": 0, "sock_bufs.socket_recv_size6": 0, "sock_bufs.socket_send_size6": 0, "peer.unreachable_peers": 0, "dht.dht_invalid_get_peers": 0, "dht.dht_invalid_announce": 0, "peer.connreset_peers": 0, "utp.utp_packets_out": 0, "net.on_read_counter": 0, "ses.num_incoming_interested": 0, "peer.num_peers_down_disk": 0, "peer.banned_for_hash_failure": 0, "disk.arc_volatile_size": 0, "peer.eof_peers": 0, "ses.num_incoming_have": 0, "ses.num_outgoing_unchoke": 0, "dht.dht_get_out": 0, "net.limiter_down_queue": 0, "dht.dht_messages_out": 0, "disk.num_write_jobs": 0, "sock_bufs.socket_recv_size16": 0, "sock_bufs.socket_recv_size17": 0, "sock_bufs.socket_recv_size20": 0, "peer.connrefused_peers": 0, "sock_bufs.socket_recv_size9": 0, "ses.num_outgoing_not_interested": 0, "sock_bufs.socket_recv_size14": 0, "peer.error_utp_peers": 0, "sock_bufs.socket_send_size14": 0, "sock_bufs.socket_send_size9": 0, "utp.num_utp_connected": 0, "picker.piece_picker_suggest_loops": 0, "ses.waste_piece_closing": 0, "disk.disk_job_time": 0, "net.recv_failed_bytes": 0, "sock_bufs.socket_send_size11": 0, "dht.dht_announce_peer_in": 0, "sock_bufs.socket_recv_size8": 0, "ses.num_incoming_reject": 0, "peer.num_peers_up_disk": 0, "disk.arc_mru_size": 0, "utp.utp_packet_resend": 0, "dht.dht_get_peers_out": 0, "dht.dht_messages_out_dropped": 0, "utp.utp_payload_pkts_out": 0, "net.on_disk_queue_counter": 0, "dht.dht_put_in": 0, "ses.num_incoming_dht_port": 0, "picker.piece_picker_rand_loops": 0, "peer.num_ssl_socks5_peers": 0, "ses.num_incoming_extended": 0, "peer.num_i2p_peers": 0, "utp.utp_packets_in": 0, "utp.utp_samples_below_target": 0, "peer.connection_attempts": 0, "disk.queued_disk_jobs": 0, "peer.transport_timeout_peers": 0, "ses.num_piece_passed": 0, "peer.connection_attempt_loops": 0, "peer.num_banned_peers": 0, "ses.num_queued_seeding_torrents": 0, "disk.num_fenced_hash": 0, "ses.num_outgoing_have_all": 0, "net.sent_bytes": 0, "ses.num_stopped_torrents": 0, "disk.num_fenced_flush_hashed": 0, "ses.num_outgoing_allowed_fast": 0, "ses.num_incoming_choke": 0, "peer.piece_rejects": 0, "ses.num_incoming_piece": 0, "disk.num_blocks_read": 0, "disk.num_fenced_clear_piece": 0, "ses.non_filter_torrents": 0, "sock_bufs.socket_recv_size15": 0, "peer.error_rc4_peers": 0, "peer.incoming_connections": 0, "disk.num_read_jobs": 0, "ses.num_outgoing_pex": 0, "dht.dht_put_out": 0, "disk.num_read_back": 0, "ses.num_total_pieces_added": 256, "utp.num_utp_close_wait": 0, "peer.notconnected_peers": 0, "peer.num_peers_down_unchoked": 0, "disk.num_fenced_read": 0, "peer.connaborted_peers": 0, "sock_bufs.socket_send_size10": 0, "sock_bufs.socket_recv_size18": 0, "disk.disk_hash_time": 0, "peer.no_access_peers": 0, "peer.num_ssl_utp_peers": 0, "sock_bufs.socket_send_size3": 0, "peer.buffer_peers": 0, "disk.disk_read_time": 0, "dht.dht_announce_peer_out": 0, "peer.uninteresting_peers": 0, "ses.num_incoming_suggest": 0, "peer.num_socks5_peers": 0, "ses.num_loaded_torrents": 1, "dht.dht_allocated_observers": 0, "ses.num_have_pieces": 0, "disk.num_fenced_move_storage": 0, "disk.arc_mfu_ghost_size": 0, "sock_bufs.socket_send_size4": 0, "net.on_accept_counter": 0, "sock_bufs.socket_recv_size11": 0, "dht.dht_node_cache": 0, "sock_bufs.socket_recv_size3": 0, "disk.num_fenced_rename_file": 0, "sock_bufs.socket_send_size16": 0, "utp.num_utp_idle": 0, "picker.piece_picker_rare_loops": 0, "ses.num_pinned_torrents": 1, "net.has_incoming_connections": 0, "utp.num_utp_fin_sent": 0, "disk.blocked_disk_jobs": 0, "ses.num_outgoing_metadata": 0, "ses.waste_piece_timed_out": 0, "sock_bufs.socket_send_size7": 0, "disk.arc_mfu_size": 0, "sock_bufs.socket_send_size8": 0, "net.recv_payload_bytes": 0, "picker.snubbed_piece_picks": 0, "disk.disk_write_time": 0, "ses.num_queued_download_torrents": 0, "sock_bufs.socket_send_size15": 0, "picker.hash_fail_piece_picks": 0, "disk.num_fenced_delete_files": 0, "sock_bufs.socket_recv_size19": 0, "ses.num_incoming_have_all": 0, "peer.cancelled_piece_requests": 0, "disk.write_cache_blocks": 0, "dht.dht_ping_out": 0, "disk.request_latency": 0, "ses.num_incoming_bitfield": 0, "picker.incoming_piece_picks": 0, "peer.error_outgoing_peers": 0, "ses.num_incoming_request": 0, "disk.num_fenced_tick_storage": 0, "ses.num_incoming_metadata": 0, "ses.num_outgoing_reject": 0, "peer.error_incoming_peers": 0, "sock_bufs.socket_recv_size13": 0}
```

### /session/dht
#### GET

Returns a boolean indicating if DHT is running or not.

```shell
$ curl -i -X GET http://localhost:8080/session/dht
HTTP/1.1 200 OK
CONTENT-TYPE: application/json; charset=utf-8
CONTENT-LENGTH: 4
DATE: Thu, 18 Feb 2016 03:10:16 GMT
SERVER: Python/3.5 aiohttp/0.21.0

true
```

Torrent
--------

A torrent resource contains all the information you would need to know about a torrent.

### /torrent
#### GET

Returns a list of all info-hashes in the session.

**Example**

```shell
$ curl -i -X GET http://localhost:8080/torrent
HTTP/1.1 200 OK
CONTENT-TYPE: application/json; charset=utf-8
CONTENT-LENGTH: 44
DATE: Wed, 17 Feb 2016 04:13:15 GMT
SERVER: Python/3.5 aiohttp/0.21.0

["44a040be6d74d8d290cd20128788864cbf770719"]
```

#### POST

Add a torrent to the session.

There are three ways to add a torrent to the session using one of these three
keys: **file**, **url** or **info_hash**.

All of the methods can use the **args** key to set any options, see
http://libtorrent.org/reference-Session.html#add_torrent_params for reference.
The **args** value should be a JSON encoded dictionary.

Upon success, you will receive a 201 response and a dictionary with the info_hash in the body.  The LOCATION
header will also be set in the response for the new torrent resource.

##### File Upload

Adding a torrent by uploading a torrent file requires the use of a multipart/form-data post with the file contents keyed as **file**.

**Example**

```shell
$ curl -i -X POST -F "file=@random_one_file.torrent" -F 'args={"save_path": "/tmp"}' http://localhost:8080/torrent

HTTP/1.1 100 Continue

HTTP/1.1 201 Created
LOCATION: http://localhost:8080/torrent/44a040be6d74d8d290cd20128788864cbf770719
CONTENT-TYPE: application/json; charset=utf-8
CONTENT-LENGTH: 57
DATE: Thu, 18 Feb 2016 04:22:28 GMT
SERVER: Python/3.5 aiohttp/0.21.0

{"info_hash": "44a040be6d74d8d290cd20128788864cbf770719"}
```

##### URL

Adding a torrent by url is done by setting the **url** key.

**Example**

```shell
$ curl -i -X POST -d "url=https://www.archlinux.org/releng/releases/2016.02.01/torrent/" -d 'args={"save_path": "/tmp"}' http://localhost:8080/torrent

HTTP/1.1 201 Created
LOCATION: http://localhost:8080/torrent/88066b90278f2de655ee2dd44e784c340b54e45c
CONTENT-TYPE: application/json; charset=utf-8
CONTENT-LENGTH: 57
DATE: Fri, 19 Feb 2016 04:34:23 GMT
SERVER: Python/3.5 aiohttp/0.21.0

{"info_hash": "88066b90278f2de655ee2dd44e784c340b54e45c"}
```

##### Info-hash

Adding a torrent by info-hash is done by setting the **info_hash** key.

**Example**

```shell
$ curl -i -X POST -d "info_hash=88066b90278f2de655ee2dd44e784c340b54e45c" -d 'args={"save_path": "/tmp"}' http://localhost:8080/torrent

HTTP/1.1 201 Created
LOCATION: http://localhost:8080/torrent/88066b90278f2de655ee2dd44e784c340b54e45c
CONTENT-TYPE: application/json; charset=utf-8
CONTENT-LENGTH: 57
DATE: Wed, 24 Feb 2016 05:03:12 GMT
SERVER: Python/3.5 aiohttp/0.21.0

{"info_hash": "88066b90278f2de655ee2dd44e784c340b54e45c"}
```

#### DELETE

Remove all torrents from the session.

Optionally, the downloaded files can be deleted when the torrent is removed by adding
the **delete_files** key to the query string.

**Example**
```shell
$ curl -i -X DELETE http://localhost:8080/torrent?delete_files
HTTP/1.1 200 OK
CONTENT-LENGTH: 0
DATE: Sun, 28 Feb 2016 22:34:51 GMT
SERVER: Python/3.5 aiohttp/0.21.0
```

### /torrent/\<info-hash\>
#### GET

Returns a status dictionary for the torrent.

**Example**

```shell
$ curl -i -X GET http://localhost:8080/torrent/44a040be6d74d8d290cd20128788864cbf770719
HTTP/1.1 200 OK
CONTENT-TYPE: application/json; charset=utf-8
CONTENT-LENGTH: 3627
DATE: Wed, 17 Feb 2016 04:12:20 GMT
SERVER: Python/3.5 aiohttp/0.21.0

{"seeding_time": 0, "num_seeds": 0, "all_time_download": 0, "seed_rank": 0, "total_download": 0, "errc": {"message": "Success", "value": 0, "category": {"message": "Success", "name": "system"}}, "distributed_copies": -1.0, "download_payload_rate": 0, "priority": 0, "total_wanted": 4194304, "progress_ppm": 0, "has_metadata": true, "total_done": 0, "num_incomplete": -1, "time_since_download": -1, "block_size": 16384, "num_uploads": 0, "verified_pieces": [], "total_payload_upload": 0, "state": "downloading", "queue_position": 0, "ip_filter_applies": true, "current_tracker": "", "super_seeding": false, "last_seen_complete": 0, "is_seeding": false, "time_since_upload": -1, "moving_storage": false, "announcing_to_lsd": true, "download_rate": 0, "added_time": 1455682321, "distributed_fraction": -1, "storage_mode": 1, "auto_managed": true, "sequential_download": false, "num_connections": 0, "upload_mode": false, "upload_rate": 0, "error_file": -1, "stop_when_ready": false, "next_announce": "0.0", "total_upload": 0, "up_bandwidth_queue": 0, "is_loaded": true, "pieces": [false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false], "connections_limit": -1, "list_seeds": 0, "announcing_to_trackers": true, "total_failed_bytes": 0, "active_time": 17, "announcing_to_dht": true, "distributed_full_copies": -1, "down_bandwidth_queue": 0, "need_save_resume": true, "upload_payload_rate": 0, "num_complete": -1, "connect_candidates": 0, "total_payload_download": 0, "total_redundant_bytes": 0, "total_wanted_done": 0, "is_finished": false, "seed_mode": false, "progress": 0.0, "paused": false, "has_incoming": false, "all_time_upload": 0, "completed_time": 0, "finished_time": 0, "name": "tmprandomfile", "uploads_limit": -1, "last_scrape": -1, "info_hash": "44a040be6d74d8d290cd20128788864cbf770719", "num_peers": 0, "num_pieces": 0, "save_path": "/tmp", "share_mode": false, "list_peers": 0}
```

#### DELETE

Remove torrent from the session.

Optionally, the downloaded files can be deleted when the torrent is removed by adding
the **delete_files** key to the query string.

**Example**

```shell
$ curl -i -X DELETE http://localhost:8080/torrent/88066b90278f2de655ee2dd44e784c340b54e45c?delete_files
HTTP/1.1 200 OK
CONTENT-LENGTH: 0
DATE: Fri, 26 Feb 2016 06:03:01 GMT
SERVER: Python/3.5 aiohttp/0.21.0
```
