#
# spritzle/torrent.py
#
# Copyright (C) 2016 Andrew Resch <andrewresch@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.    If not, write to:
#   The Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor
#   Boston, MA    02110-1301, USA.

import asyncio
from base64 import b64decode
import binascii
import functools
import ipaddress
import json
from json import JSONDecodeError
import logging
import operator
import os
from pathlib import Path
import re
import socket
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse


import aiohttp
from aiohttp import web

import spritzle.daemon.common as common
from spritzle.daemon.keys import APP_KEY_CONFIG, APP_KEY_CORE
from spritzle.daemon.torrent import AlertException

import libtorrent as lt

log = logging.getLogger("spritzle")
routes = web.RouteTableDef()


def validate_torrent_url(url_str: str, allow_loopback: bool = False) -> str:
    parsed = urlparse(url_str)
    if parsed.scheme == "magnet":
        return url_str
    if parsed.scheme not in ("http", "https"):
        raise web.HTTPBadRequest(
            reason=f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP, HTTPS, and magnet are allowed."
        )
    if not parsed.hostname:
        raise web.HTTPBadRequest(reason="Invalid URL: missing hostname.")

    hostname = parsed.hostname.lower()
    if not allow_loopback and hostname in ("localhost", "localhost.localdomain"):
        raise web.HTTPBadRequest(reason=f"URL host '{parsed.hostname}' is not allowed.")

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_link_local or ip.is_multicast:
            raise web.HTTPBadRequest(reason=f"URL host '{parsed.hostname}' is not allowed.")
        if not allow_loopback and (ip.is_loopback or ip.is_private):
            raise web.HTTPBadRequest(reason=f"URL host '{parsed.hostname}' is not allowed.")
    except ValueError:
        if not allow_loopback:
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                for family, _, _, _, sockaddr in addr_info:
                    ip = ipaddress.ip_address(sockaddr[0])
                    if ip.is_link_local or ip.is_multicast or ip.is_loopback or ip.is_private:
                        raise web.HTTPBadRequest(
                            reason=f"URL host '{parsed.hostname}' resolves to a disallowed address."
                        )
            except socket.gaierror:
                pass

    return url_str




def get_valid_handle(core, tid):
    """
    Either returns a valid torrent_handle or aborts with a client-error (400/404)
    """
    try:
        raw_hash = binascii.unhexlify(tid)
        if len(raw_hash) != 20:
            raise web.HTTPBadRequest(reason=f"Invalid info-hash length: {tid}")
        sha = lt.sha1_hash(raw_hash)
    except (binascii.Error, ValueError):
        raise web.HTTPBadRequest(reason=f"Invalid info-hash format: {tid}")

    handle = core.session.find_torrent(sha)
    if not handle.is_valid():
        raise web.HTTPNotFound(reason="Torrent not found: " + tid)

    return handle



VALID_QUERY_OPS = {"eq", "lt", "gt", "ne", "ge", "le", "all", "any", "in"}
VALID_LT_STATUS_KEYS = {x for x in dir(lt.torrent_status) if not x.startswith("_")}
VALID_STATUS_KEYS = VALID_LT_STATUS_KEYS | {"last_error", "info_hash"}


def _to_bool(val: Any) -> bool:
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    return bool(val)


def get_torrent_list(core, query=None) -> List[Any]:
    query_dict = dict(query) if query else {}
    keys_raw = query_dict.pop("keys", None)
    if keys_raw is None:
        keys_raw = query_dict.pop("fields", None)

    if keys_raw is None:
        if not query_dict:
            # No query string was provided, so just return a list of all
            # the torrents.
            return [str(th.info_hash()) for th in core.session.get_torrents()]

        keys = {"info_hash"}
        for k in query_dict.keys():
            if "." in k and k.rsplit(".", 1)[-1] in VALID_QUERY_OPS:
                keys.add(k.rsplit(".", 1)[0])
            else:
                keys.add(k)

        statuses: List[Dict[str, Any]] = []
        for handle in core.session.get_torrents():
            info_hash = str(handle.info_hash())
            fetch_k = list(keys)
            if "state" in fetch_k:
                fetch_k = list(set(fetch_k) | {"paused", "flags"})
            st = common.struct_to_dict(handle.status(), only_keys=fetch_k)
            if info_hash in core.torrent_data:
                st.update(core.torrent_data[info_hash])
            statuses.append(st)

        return get_torrent_list_by_query(query_dict, statuses)

    # 'keys' or 'fields' parameter was specified for bulk status retrieval
    keys_list = [k.strip() for k in str(keys_raw).split(",") if k.strip()]
    if "all" in keys_list or "*" in keys_list:
        requested_keys = None
    else:
        requested_keys = keys_list
        for k in requested_keys:
            if (
                k not in VALID_STATUS_KEYS
                and not k.startswith("spritzle.")
            ):
                raise web.HTTPBadRequest(reason=f"Field {k} is not valid.")

    fetch_keys = None
    if requested_keys is not None:
        fetch_keys = set(requested_keys) | {"info_hash"}
        for k in query_dict.keys():
            if "." in k and k.rsplit(".", 1)[-1] in VALID_QUERY_OPS:
                fetch_keys.add(k.rsplit(".", 1)[0])
            else:
                fetch_keys.add(k)
        if "state" in fetch_keys:
            fetch_keys.update(["paused", "flags"])

    statuses = []
    for handle in core.session.get_torrents():
        info_hash = str(handle.info_hash())
        st = common.struct_to_dict(
            handle.status(),
            only_keys=list(fetch_keys) if fetch_keys is not None else None,
        )
        if info_hash in core.torrent_data:
            st.update(core.torrent_data[info_hash])
        if "info_hash" not in st:
            st["info_hash"] = info_hash
        statuses.append(st)

    if query_dict:
        matched = get_torrent_list_by_query(query_dict, statuses, return_statuses=True)
    else:
        matched = statuses

    if requested_keys is not None:
        keep_keys = set(requested_keys) | {"info_hash"}
        return [{k: v for k, v in item.items() if k in keep_keys} for item in matched]
    return matched


def get_torrent_list_by_query(query, statuses, return_statuses: bool = False) -> List[Any]:
    torrents: List[Any] = []

    all_status_keys = set()
    for s in statuses:
        all_status_keys.update(s.keys())

    parsed_queries = []
    for raw_key, value in query.items():
        if not isinstance(raw_key, str):
            raise web.HTTPBadRequest(reason=f"Key {raw_key} must be string type.")
        if not isinstance(value, str):
            raise web.HTTPBadRequest(reason=f"Value {value} must be string type.")

        if "." in raw_key and raw_key.rsplit(".", 1)[-1] in VALID_QUERY_OPS:
            op = raw_key.rsplit(".", 1)[-1]
            key = raw_key.rsplit(".", 1)[0]
        else:
            op = ""
            key = raw_key

        if (
            key not in all_status_keys
            and key not in VALID_STATUS_KEYS
            and not key.startswith("spritzle.")
        ):
            raise web.HTTPBadRequest(reason=f"Field {key} is not valid.")

        parsed_queries.append((key, op, value))

    if len(statuses) == 0:
        return []

    regex_cache: Dict[str, re.Pattern] = {}

    def get_pattern(pattern_str: str) -> re.Pattern:
        if pattern_str not in regex_cache:
            try:
                regex_cache[pattern_str] = re.compile(pattern_str)
            except re.error as ex:
                raise web.HTTPBadRequest(
                    reason=f"Invalid regular expression '{pattern_str}': {ex}"
                )
        return regex_cache[pattern_str]

    for status in statuses:
        for key, op, value in parsed_queries:
            if key not in status:
                if op == "ne":
                    continue
                break

            if isinstance(status[key], str):
                ops = {"", "eq", "ne"}
                if op not in ops:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid operator {op}, must provide valid operator: {sorted(ops)}"
                    )
                target_val = status[key]
                if key == "state" and (status.get("paused") is True or (int(status.get("flags", 0)) & 16) != 0):
                    target_val = "paused"
                pat = get_pattern(value)
                matched = bool(pat.match(target_val))
                if op == "ne" and matched:
                    break
                elif op in ("", "eq") and not matched:
                    break

            elif isinstance(status[key], bool):
                ops = {"", "eq", "ne"}
                if op not in ops:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid operator {op}, must provide valid operator: {sorted(ops)}"
                    )
                m = re.match(r"(?P<value>^true$|^false$)", value)
                if m is None:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid query for boolean type: {key}={value}, value must be either 'true' or 'false'."
                    )
                target = (m.group("value") == "true")
                if op in ("", "eq") and status[key] != target:
                    break
                elif op == "ne" and status[key] == target:
                    break


            elif isinstance(status[key], int) or isinstance(status[key], float):
                ops = {
                    "": operator.eq,
                    "eq": operator.eq,
                    "lt": operator.lt,
                    "gt": operator.gt,
                    "ne": operator.ne,
                    "ge": operator.ge,
                    "le": operator.le,
                }
                if op not in ops:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid operator {op}, must provide valid operator: {list(ops.keys())}"
                    )
                try:
                    num_val = float(value)
                except ValueError:
                    raise web.HTTPBadRequest(reason=f"Invalid numeric value '{value}' for field '{key}'.")
                if not ops[op](status[key], num_val):
                    break
            elif isinstance(status[key], list):
                ops = {"", "all", "any", "in", "ne"}
                if op not in ops:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid operator {op}, must provide valid operator: {sorted(ops)}"
                    )

                items = [str(x) for x in status[key]]
                if op in ("", "any"):
                    pat = get_pattern(value)
                    if not any(pat.match(item) for item in items):
                        break
                elif op == "ne":
                    pat = get_pattern(value)
                    if any(pat.match(item) for item in items):
                        break
                elif op == "in":
                    targets = [v.strip() for v in value.split(",")]
                    if not any(item in targets for item in items):
                        break
                elif op == "all":
                    targets = [v.strip() for v in value.split(",")]
                    if not all(target in items for target in targets):
                        break
            else:
                if op == "ne":
                    continue
                break

        else:
            if return_statuses:
                torrents.append(status)
            else:
                torrents.append(status["info_hash"])

    return torrents


def get_torrent_files(handle: Any) -> List[Dict[str, Any]]:
    ti = handle.torrent_file() if handle.is_valid() else None
    if not ti:
        return []
    fs = ti.files()
    num = ti.num_files()
    try:
        progresses = handle.file_progress()
    except Exception:
        progresses = []
    try:
        priorities = handle.get_file_priorities()
    except Exception:
        priorities = []

    files = []
    for i in range(num):
        size = fs.file_size(i)
        done = progresses[i] if i < len(progresses) else 0
        prio = priorities[i] if i < len(priorities) else 4
        prog = (done / size) if size > 0 else 1.0
        files.append({
            "index": i,
            "path": fs.file_path(i),
            "size": size,
            "done": done,
            "progress": round(prog, 4),
            "priority": prio,
        })
    return files


def get_torrent_peers(handle: Any) -> List[Dict[str, Any]]:
    try:
        peer_infos = handle.get_peer_info()
    except Exception:
        return []

    peers = []
    for p in peer_infos:
        ip_str = p.ip[0] if isinstance(p.ip, (tuple, list)) and len(p.ip) > 0 else ""
        port = p.ip[1] if isinstance(p.ip, (tuple, list)) and len(p.ip) > 1 else 0
        client = ""
        if getattr(p, "client", None):
            client = (
                p.client.decode("utf-8", errors="replace").strip("\x00 \t\r\n")
                if isinstance(p.client, bytes)
                else str(p.client).strip("\x00 \t\r\n")
            )
        if not client and getattr(p, "pid", None):
            try:
                identify_fn = getattr(lt, "identify_client", None)
                if identify_fn:
                    identified = identify_fn(p.pid).strip()
                    if identified and identified != "Unknown" and not identified.startswith("Unknown [00000000"):
                        client = identified
            except Exception:
                pass
        if not client:
            flags = getattr(p, "flags", 0)
            peer_info_cls = getattr(lt, "peer_info", None)
            handshake_flag = getattr(peer_info_cls, "handshake", 64) if peer_info_cls else 64
            connecting_flag = getattr(peer_info_cls, "connecting", 128) if peer_info_cls else 128
            if flags & handshake_flag:
                client = "<handshaking>"
            elif flags & connecting_flag:
                client = "<connecting>"
            else:
                client = "<unknown>"
        peers.append({
            "ip": f"{ip_str}:{port}" if port else ip_str,
            "host": ip_str,
            "port": port,
            "client": client,
            "down_speed": int(p.down_speed),
            "up_speed": int(p.up_speed),
            "progress": round(float(p.progress), 4),
            "total_download": int(p.total_download),
            "total_upload": int(p.total_upload),
            "flags": int(p.flags),
            "source": int(p.source),
        })
    return peers


def get_torrent_trackers(handle: Any) -> List[Dict[str, Any]]:
    try:
        raw_trackers = handle.trackers()
    except Exception:
        return []

    trackers = []
    for tr in raw_trackers:
        if isinstance(tr, dict):
            item = dict(tr)
            if "last_error" in item and hasattr(item["last_error"], "value"):
                item["last_error"] = {
                    "value": item["last_error"].value(),
                    "message": item["last_error"].message(),
                }
            trackers.append(item)
        else:
            item = common.struct_to_dict(tr)
            trackers.append(item)
    return trackers


@routes.get("/torrent")
@routes.get("/torrent/{tid}")
async def get_torrent(request):
    core = request.app[APP_KEY_CORE]
    tid = request.match_info.get("tid", None)

    if tid is None:
        return web.json_response(get_torrent_list(core, request.query))
    else:
        handle = get_valid_handle(core, tid)

        status = common.struct_to_dict(handle.status())

        info_hash = str(handle.info_hash())
        if info_hash in core.torrent_data:
            status.update(core.torrent_data[info_hash])

        query = request.query
        detail = query.get("detail")
        expand = [x.strip() for x in query.get("expand", "").split(",") if x.strip()]
        include_full = detail in ("full", "all", "1", "true")

        ti = handle.torrent_file() if handle.is_valid() else None
        if ti:
            status["total_pieces"] = ti.num_pieces()
            status["piece_length"] = ti.piece_length()
            status["num_files"] = ti.num_files()

        if include_full or "files" in expand or "files" in query:
            status["files"] = get_torrent_files(handle)
        if include_full or "peers" in expand or "peers" in query:
            status["peers"] = get_torrent_peers(handle)
        if include_full or "trackers" in expand or "trackers" in query:
            status["trackers"] = get_torrent_trackers(handle)

        return web.json_response(status)


@routes.get("/torrent/{tid}/files")
async def get_torrent_files_endpoint(request):
    core = request.app[APP_KEY_CORE]
    tid = request.match_info["tid"]
    handle = get_valid_handle(core, tid)
    return web.json_response(get_torrent_files(handle))


@routes.get("/torrent/{tid}/peers")
async def get_torrent_peers_endpoint(request):
    core = request.app[APP_KEY_CORE]
    tid = request.match_info["tid"]
    handle = get_valid_handle(core, tid)
    return web.json_response(get_torrent_peers(handle))


@routes.get("/torrent/{tid}/trackers")
async def get_torrent_trackers_endpoint(request):
    core = request.app[APP_KEY_CORE]
    tid = request.match_info["tid"]
    handle = get_valid_handle(core, tid)
    return web.json_response(get_torrent_trackers(handle))


@routes.post("/torrent")
async def post_torrent(request):
    """
    libtorrent requires one of these three fields: ti, url, info_hash
    The save_path field is always required.

    Since the ti field isn't feasible to use over rpc we will ignore it.
    Instead, we will look for any uploaded files in the POST and create
    the torrent_info object based on the file data.

    http://libtorrent.org/reference-Session.html#add_torrent_params
    """
    core = request.app[APP_KEY_CORE]
    config = request.app[APP_KEY_CONFIG]

    atp_dict: Dict[str, Any] = {"save_path": config.get("default_save_path", "")}
    magnet_params: Optional[lt.add_torrent_params] = None

    try:
        post = await request.json()
    except JSONDecodeError as ex:
        raise web.HTTPBadRequest(reason="Invalid JSON", text=ex.msg)

    if not isinstance(post, dict):
        raise web.HTTPBadRequest(reason="Request body must be a JSON object.")

    # We require that only one of file, url or info_hash is set
    if len(set(post.keys()).intersection(("file", "url", "info_hash"))) != 1:
        raise web.HTTPBadRequest(
            reason="One of and only one 'file', 'url' or 'info_hash' allowed."
        )

    def generate_torrent_info(data):
        try:
            atp_dict["ti"] = lt.torrent_info(lt.bdecode(data))
        except (RuntimeError, TypeError, ValueError) as e:
            raise web.HTTPBadRequest(reason=f"Not a valid torrent file: {e}")

    if "file" in post:
        try:
            raw_file = post.pop("file")
            if not isinstance(raw_file, (str, bytes)):
                raise ValueError("file must be a base64 encoded string")
            data = b64decode(raw_file)
        except (binascii.Error, ValueError, TypeError) as ex:
            raise web.HTTPBadRequest(reason=f"Invalid base64 file data: {ex}")
        generate_torrent_info(data)
    # We do not use libtorrent's ability to download torrents as it will
    # probably be removed in future versions and cannot provide the
    # info-hash when we need it.
    # See: https://github.com/arvidn/libtorrent/issues/481
    elif "url" in post:
        raw_url = post.pop("url")
        allow_loopback = _to_bool(
            config.get("allow_loopback_urls", False)
        ) or _to_bool(os.environ.get("SPRITZLE_ALLOW_LOOPBACK_URL", False))
        validated_url = validate_torrent_url(raw_url, allow_loopback=allow_loopback)
        if validated_url.startswith("magnet:"):
            try:
                magnet_params = lt.parse_magnet_uri(validated_url)
            except Exception as ex:
                raise web.HTTPBadRequest(reason=f"Invalid magnet URI: {ex}")
            if not getattr(magnet_params, "save_path", None):
                magnet_params.save_path = atp_dict.get("save_path", "")
        else:
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as client:
                    async with client.get(validated_url) as resp:
                        if resp.status != 200:
                            raise web.HTTPBadRequest(
                                reason=f"Failed to fetch torrent URL (HTTP {resp.status})"
                            )
                        generate_torrent_info(await resp.read())
            except aiohttp.ClientError as ex:
                raise web.HTTPBadRequest(reason=f"Error fetching torrent URL: {ex}")

    elif "info_hash" in post:
        raw_info_hash = post.pop("info_hash")
        if not isinstance(raw_info_hash, str):
            raise web.HTTPBadRequest(reason="info_hash must be a hex string")
        try:
            info_hash_bytes = binascii.unhexlify(raw_info_hash)
            if len(info_hash_bytes) not in (20, 32):
                raise web.HTTPBadRequest(
                    reason=f"Invalid info-hash length: {raw_info_hash}"
                )
            atp_dict["info_hashes"] = info_hash_bytes
        except (binascii.Error, ValueError) as ex:
            raise web.HTTPBadRequest(reason=f"Invalid hex info-hash: {ex}")

    tags = post.pop("spritzle.tags", [])
    if tags is None:
        tags = []
    elif not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise web.HTTPBadRequest(reason="'spritzle.tags' must be a list of strings.")

    raw_save_path = str(
        post.get("save_path")
        or (getattr(magnet_params, "save_path", None) if magnet_params is not None else None)
        or atp_dict.get("save_path")
        or config.get("default_save_path", "")
    )

    def prepare_save_path(sp: str) -> str:
        expanded = os.path.expanduser(sp.strip()) if sp else str(Path.home() / "Downloads")
        p = Path(expanded).resolve()
        if p.exists() and not p.is_dir():
            raise ValueError(f"Save path '{p}' exists and is not a directory.")
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            raise OSError(f"Cannot create save path directory '{p}': {err}")
        if not os.access(p, os.W_OK | os.X_OK):
            raise PermissionError(f"Save path directory '{p}' is not writable.")
        return str(p)

    try:
        canonical_save_path = await asyncio.get_running_loop().run_in_executor(
            None, prepare_save_path, raw_save_path
        )
    except (ValueError, OSError, PermissionError) as e:
        raise web.HTTPBadRequest(reason=str(e))

    atp_dict["save_path"] = canonical_save_path
    if magnet_params is not None:
        magnet_params.save_path = canonical_save_path
    if "save_path" in post:
        post["save_path"] = canonical_save_path

    # We have already popped all spritzle specific options from post, merge it in
    atp: Union[Dict[str, Any], lt.add_torrent_params]
    if magnet_params is not None:
        atp = magnet_params
        for k, v in post.items():
            try:
                setattr(atp, k, v)
            except Exception:
                pass
    else:
        atp = atp_dict
        atp.update(post)

    try:
        torrent_handle = await asyncio.get_running_loop().run_in_executor(
            None, functools.partial(core.session.add_torrent), atp
        )
    except (KeyError, TypeError, ValueError) as e:
        raise web.HTTPBadRequest(reason=str(e))
    except RuntimeError as e:
        if "duplicate" in str(e).lower():
            raise web.HTTPConflict(reason=f"Duplicate torrent: {e}")
        raise web.HTTPInternalServerError(reason=f"Error in session.add_torrent(): {e}")

    info_hash = str(torrent_handle.info_hash())
    if info_hash not in core.torrent_data:
        core.torrent_data[info_hash] = {}
    core.torrent_data[info_hash]["spritzle.tags"] = tags
    try:
        await asyncio.wait_for(core.resume_data.save_torrent(torrent_handle), timeout=15.0)
    except asyncio.TimeoutError:
        log.warning(f"Timed out waiting for initial resume data save for {info_hash}")

    st = common.struct_to_dict(torrent_handle.status())
    name = st.get("name", "")
    size = st.get("total_wanted", 0) or st.get("total_size", 0)

    return web.json_response(
        {
            "info_hash": info_hash,
            "name": name,
            "size": size,
            "save_path": canonical_save_path,
            "state": st.get("state", "downloading"),
            "num_peers": st.get("num_peers", 0),
        },
        status=201,
        headers={"Location": f"{request.scheme}://{request.host}/torrent/{info_hash}"},
    )


@routes.put("/torrent/{tid}/flags")
@routes.put("/torrent/{tid}/flags/{flag}")
async def put_flags(request):
    core = request.app[APP_KEY_CORE]
    tid = request.match_info.get("tid")
    flag = request.match_info.get("flag", None)
    handle = get_valid_handle(core, tid)

    try:
        body = await request.json()
    except Exception as ex:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {ex}")

    if flag:
        body = {flag: body}

    if not isinstance(body, dict):
        raise web.HTTPBadRequest(reason="Request body must be a JSON object.")

    flags = 0
    mask = 0
    for k, v in body.items():
        if k not in get_lt_torrent_flags():
            raise web.HTTPBadRequest(
                reason=f"{k} is not a valid libtorrent torrent_flag"
            )
        fvalue = getattr(lt.torrent_flags, k)
        val_bool = bool(v)
        if isinstance(v, str):
            val_bool = v.strip().lower() in ("true", "1", "yes", "on")
        if val_bool:
            flags |= fvalue
        mask |= fvalue
    handle.set_flags(flags, mask)

    return web.json_response()


def get_lt_torrent_flags() -> List[str]:
    return [
        f
        for f in dir(lt.torrent_flags)
        if not f.startswith("_") and f != "default_flags"
    ]


def build_flags_dict(flags: int) -> Dict[str, bool]:
    ret = {}
    for f in get_lt_torrent_flags():
        ret[f] = bool(flags & getattr(lt.torrent_flags, f))
    return ret


@routes.get("/torrent/{tid}/flags")
@routes.get("/torrent/{tid}/flags/{flag}")
async def get_flags(request):
    core = request.app[APP_KEY_CORE]
    tid = request.match_info.get("tid")
    flag = request.match_info.get("flag", None)
    handle = get_valid_handle(core, tid)

    if flag is None:
        ret = build_flags_dict(handle.flags())
    elif flag not in get_lt_torrent_flags():
        raise web.HTTPNotFound(reason=f"{flag} is not a valid libtorrent torrent_flag")
    else:
        ret = bool(handle.flags() & getattr(lt.torrent_flags, flag))

    return web.json_response(ret)


@routes.delete("/torrent")
@routes.delete("/torrent/{tid}")
async def delete_torrent(request):
    core = request.app[APP_KEY_CORE]
    tid = request.match_info.get("tid", None)

    # see libtorrent.options_t for valid options
    options = 0
    query_params = {}

    for key, val in request.query.items():
        if hasattr(lt.options_t, key):
            if val.strip().lower() in ("false", "0", "no", "off"):
                continue
            options = options | getattr(lt.options_t, key)
        else:
            query_params[key] = val

    if tid is not None:
        handle = get_valid_handle(core, tid)
        info_hash = str(handle.info_hash())
        try:
            try:
                await core.torrent.remove(handle, options)
            except AlertException as ex:
                msg = ex.alert.message() if hasattr(ex.alert, "message") else str(ex)
                log.error(f"Error deleting files for torrent {info_hash}: {msg}")
            except asyncio.TimeoutError:
                log.error(f"Timed out removing torrent {tid}")
                raise web.HTTPGatewayTimeout(text=f"Timed out removing torrent {tid}")
        finally:
            core.resume_data.delete(info_hash)
            core.torrent_data.pop(info_hash, None)
        return web.Response()

    # Bulk deletion
    query_params.pop("keys", None)
    query_params.pop("fields", None)
    tids = get_torrent_list(core, query=query_params if query_params else None)
    sem = asyncio.Semaphore(64)

    async def _remove_one(t: Any):
        async with sem:
            tid = t["info_hash"] if isinstance(t, dict) else t
            try:
                handle = get_valid_handle(core, tid)
                info_hash = str(handle.info_hash())
                try:
                    try:
                        await core.torrent.remove(handle, options)
                    except AlertException as ex:
                        msg = ex.alert.message() if hasattr(ex.alert, "message") else str(ex)
                        log.error(f"Error deleting files for torrent {info_hash}: {msg}")
                    except asyncio.TimeoutError:
                        log.error(f"Timed out removing torrent {tid}")
                    except Exception as e:
                        log.error(f"Error removing torrent {tid}: {e}")
                finally:
                    core.resume_data.delete(info_hash)
                    core.torrent_data.pop(info_hash, None)
            except web.HTTPException:
                log.warning(f"Skipping missing torrent {tid} during bulk removal")

    if tids:
        await asyncio.gather(*[_remove_one(t) for t in tids])

    return web.Response()



ALLOWED_TORRENT_METHODS = {
    "pause",
    "resume",
    "force_recheck",
    "force_reannounce",
    "force_dht_announce",
    "queue_position_down",
    "queue_position_up",
    "queue_position_bottom",
    "queue_position_top",
    "set_max_uploads",
    "set_upload_limit",
    "set_download_limit",
    "set_max_connections",
    "set_sequential_download",
    "clear_error",
    "flush_cache",
    "move_storage",
}


@routes.post("/torrent/{tid}/{method}")
async def post_torrent_method(request):
    core = request.app[APP_KEY_CORE]
    tid = request.match_info.get("tid")
    method_name = request.match_info.get("method")

    if method_name not in ALLOWED_TORRENT_METHODS:
        raise web.HTTPBadRequest(reason=f"Method '{method_name}' is not allowed.")

    handle = get_valid_handle(core, tid)
    method = getattr(handle, method_name, None)
    if not method or not callable(method) or method_name.startswith("_"):
        raise web.HTTPBadRequest(reason=f"Invalid method '{method_name}'")


    try:
        body = await request.text()
    except UnicodeDecodeError as ex:
        raise web.HTTPBadRequest(reason=f"Invalid payload encoding: {ex}")
    if body:
        try:
            args = json.loads(body)
        except JSONDecodeError as ex:
            raise web.HTTPBadRequest(reason="Invalid JSON", text=ex.msg)
        if not isinstance(args, list):
            raise web.HTTPBadRequest(reason="Body must be a list of arguments.")
    else:
        args = []

    try:
        if method_name == "pause":
            if hasattr(handle, "unset_flags") and hasattr(lt, "torrent_flags"):
                handle.unset_flags(lt.torrent_flags.auto_managed)
            result = handle.pause(*args)
        elif method_name == "resume":
            if hasattr(handle, "set_flags") and hasattr(lt, "torrent_flags"):
                handle.set_flags(lt.torrent_flags.auto_managed)
            result = handle.resume(*args)
        else:
            result = method(*args)
    except Exception as ex:
        raise web.HTTPBadRequest(text=f"Something went wrong: {ex}")

    if method_name == "clear_error":
        info_hash = str(handle.info_hash())
        if info_hash in core.torrent_data:
            core.torrent_data[info_hash].pop("last_error", None)

    return web.json_response(result)
