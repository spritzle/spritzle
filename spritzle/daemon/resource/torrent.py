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
import json
from base64 import b64decode
import binascii
import functools
from json import JSONDecodeError
import ipaddress
import logging
import operator
import re
from typing import Any, Dict, List
from urllib.parse import urlparse


import aiohttp
from aiohttp import web

import spritzle.daemon.common as common
from spritzle.daemon.keys import APP_KEY_CONFIG, APP_KEY_CORE
from spritzle.daemon.torrent import AlertException

import libtorrent as lt

log = logging.getLogger("spritzle")
routes = web.RouteTableDef()


def validate_torrent_url(url_str: str) -> str:
    parsed = urlparse(url_str)
    if parsed.scheme not in ("http", "https"):
        raise web.HTTPBadRequest(
            reason=f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are allowed."
        )
    if not parsed.hostname:
        raise web.HTTPBadRequest(reason="Invalid URL: missing hostname.")

    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_link_local or ip.is_multicast:
            raise web.HTTPBadRequest(reason=f"URL host '{parsed.hostname}' is not allowed.")
    except ValueError:
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


def get_torrent_list(core, query=None) -> List[str]:
    if not query:
        # No query string was provided, so just return a list of all
        # the torrents.
        return [str(th.info_hash()) for th in core.session.get_torrents()]

    keys = {"info_hash"}
    for k in query.keys():
        if "." in k and k.rsplit(".", 1)[-1] in VALID_QUERY_OPS:
            keys.add(k.rsplit(".", 1)[0])
        else:
            keys.add(k)
    
    statuses: List[Dict[str, Any]] = []
    for handle in core.session.get_torrents():
        info_hash = str(handle.info_hash())
        st = common.struct_to_dict(handle.status(), only_keys=list(keys))
        if info_hash in core.torrent_data:
            st.update(core.torrent_data[info_hash])
        statuses.append(st)

    return get_torrent_list_by_query(query, statuses)


def get_torrent_list_by_query(query, statuses) -> List[str]:
    torrents: List[str] = []

    if len(statuses) == 0:
        return []

    for status in statuses:
        for key, value in query.items():
            # Key's can have an operator as a '.' separated suffix. If the key is in the status dict it means it's valid
            # and does not have an operator.
            if key in status:
                op = ""
            elif "." in key and key.rsplit(".", 1)[-1] in VALID_QUERY_OPS:
                op = key.rsplit(".", 1)[-1]
                key = key.rsplit(".", 1)[0]
            else:
                op = ""

            if not isinstance(key, str):
                raise web.HTTPBadRequest(reason=f"Key {key} must be string type.")
            if not isinstance(value, str):
                raise web.HTTPBadRequest(reason=f"Value {value} must be string type.")
            if key not in status:
                raise web.HTTPBadRequest(reason=f"Field {key} is not valid.")

            if isinstance(status[key], str):
                try:
                    if not re.match(value, status[key]):
                        break
                except re.error as ex:
                    raise web.HTTPBadRequest(reason=f"Invalid regular expression '{value}': {ex}")

            elif isinstance(status[key], bool):
                m = re.match(r"(?P<value>^true$|^false$)", value)
                if m is None:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid query for boolean type: {key}={value}, value must be either 'true' or 'false'."
                    )
                if m.group("value") == "true" and not status[key]:
                    break
                if m.group("value") == "false" and status[key]:
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
                ops = {"", "all", "any", "in"}
                if op not in ops:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid operator {op}, must provide valid operator: {sorted(ops)}"
                    )

                items = [str(x) for x in status[key]]
                if op in ("", "any"):
                    try:
                        if not any(re.match(value, item) for item in items):
                            break
                    except re.error as ex:
                        raise web.HTTPBadRequest(reason=f"Invalid regular expression '{value}': {ex}")
                elif op == "in":
                    targets = [v.strip() for v in value.split(",")]
                    if not any(item in targets for item in items):
                        break
                elif op == "all":
                    targets = [v.strip() for v in value.split(",")]
                    if not all(target in items for target in targets):
                        break

        else:
            torrents.append(status["info_hash"])

    return torrents


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

        if tid in core.torrent_data:
            status.update(core.torrent_data[tid])

        return web.json_response(status)


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

    atp = {"save_path": config.get("add_torrent_params.save_path", "")}

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
            atp["ti"] = lt.torrent_info(lt.bdecode(data))
        except RuntimeError as e:
            raise web.HTTPBadRequest(reason=f"Not a valid torrent file: {e}")

    if "file" in post:
        data = b64decode(post.pop("file"))
        generate_torrent_info(data)
    # We do not use libtorrent's ability to download torrents as it will
    # probably be removed in future versions and cannot provide the
    # info-hash when we need it.
    # See: https://github.com/arvidn/libtorrent/issues/481
    elif "url" in post:
        raw_url = post.pop("url")
        validated_url = validate_torrent_url(raw_url)
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
        atp["info_hashes"] = binascii.unhexlify(post.pop("info_hash"))

    if "ti" in atp:
        info_hash = str(atp["ti"].info_hash())
    elif "info_hashes" in atp:
        info_hash = binascii.hexlify(atp["info_hashes"]).decode()

    if info_hash not in core.torrent_data:
        core.torrent_data[info_hash] = {}

    tags = post.pop("spritzle.tags", [])
    core.torrent_data[info_hash]["spritzle.tags"] = tags

    # We have already popped all spritzle specific options from post, merge it in
    atp.update(post)

    try:
        torrent_handle = await asyncio.get_event_loop().run_in_executor(
            None, functools.partial(core.session.add_torrent), atp
        )
    except KeyError as e:
        raise web.HTTPBadRequest(reason=str(e))
    except RuntimeError as e:
        raise web.HTTPInternalServerError(reason=f"Error in session.add_torrent(): {e}")

    await core.resume_data.save_torrent(torrent_handle)

    return web.json_response(
        {"info_hash": info_hash},
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
        if v:
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

    for key, val in request.query.items():
        if val.strip().lower() in ("false", "0", "no", "off"):
            continue
        try:
            options = options | getattr(lt.options_t, key)
        except AttributeError:
            log.warning(f"Invalid option key: {key}")

    if tid is None:
        # If tid is None, we remove all the torrents
        tids = get_torrent_list(core)
    else:
        tids = [tid]

    for t in tids:
        try:
            handle = get_valid_handle(core, t)
            try:
                await core.torrent.remove(handle, options)
            except AlertException as ex:
                msg = ex.alert.message() if hasattr(ex.alert, "message") else str(ex)
                log.error(f"Error deleting files for torrent {t}: {msg}")
            core.resume_data.delete(t)
            core.torrent_data.pop(t, None)
        except web.HTTPException:
            if tid is not None:
                raise
            log.warning(f"Skipping missing torrent {t} during bulk removal")
        except asyncio.TimeoutError:
            log.error(f"Timed out removing torrent {t}")
            if tid is not None:
                raise web.HTTPGatewayTimeout(text=f"Timed out removing torrent {t}")
            continue
        except Exception as e:
            log.error(f"Error removing torrent {t}: {e}")
            if tid is not None:
                raise
            continue

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


    body = await request.text()
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
        result = method(*args)
    except Exception as ex:
        raise web.HTTPBadRequest(text=f"Something went wrong: {ex}")

    return web.json_response(result)
