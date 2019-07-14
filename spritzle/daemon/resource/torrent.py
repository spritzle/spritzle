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
import logging
import operator
import re
from typing import Dict, List, Union

import aiohttp
from aiohttp import web

import spritzle.daemon.common as common
from spritzle.daemon.torrent import AlertException

import libtorrent as lt

log = logging.getLogger("spritzle")
routes = web.RouteTableDef()


def get_valid_handle(core, tid):
    """
    Either returns a valid torrent_handle or aborts with a client-error (400)
    """
    handle = core.session.find_torrent(lt.sha1_hash(binascii.unhexlify(tid)))
    if not handle.is_valid():
        raise web.HTTPNotFound(reason="Torrent not found: " + tid)

    return handle


def get_torrent_list(core, query=None) -> List[str]:
    if not query:
        # No query string was provided, so just return a list of all
        # the torrents.
        return [str(th.info_hash()) for th in core.session.get_torrents()]

    statuses: List[Dict[str, Union[str, int, float]]] = []
    for handle in core.session.get_torrents():
        # TODO: only keep keys that are in query
        statuses.append(common.struct_to_dict(handle.status()))

    return get_torrent_list_by_query(query, statuses)


def get_torrent_list_by_query(query, statuses) -> List[str]:
    torrents: List[str] = []

    if len(statuses) == 0:
        return []

    for status in statuses:
        for key, value in query.items():
            if not isinstance(key, str):
                raise web.HTTPBadRequest(reason=f"Key {key} must be string type.")
            if not isinstance(value, str):
                raise web.HTTPBadRequest(reason=f"Value {value} must be string type.")
            if key not in status:
                raise web.HTTPBadRequest(reason=f"Field {key} is not valid.")

            if isinstance(status[key], str):
                if not re.match(value, status[key]):
                    break

            elif isinstance(status[key], bool):
                m = re.match(r"(?P<value>^true$|^false$)", value)
                if m is None:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid query for boolean type: {key}={value}"
                    )
                if m.group("value") == "true" and not status[key]:
                    break
                if m.group("value") == "false" and status[key]:
                    break

            elif isinstance(status[key], int) or isinstance(status[key], float):
                m = re.match(r"(?P<op>[=<>]+)\s*(?P<value>\d+(\.\d*)?)", value)
                if m is None:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid query for number type: {key}={value}"
                    )
                op, opval = m.groups()[:2]
                ops = {
                    "<": operator.lt,
                    ">": operator.gt,
                    "=": operator.eq,
                    "!=": operator.ne,
                    ">=": operator.ge,
                    "<=": operator.le,
                }
                if op not in ops:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid operator {op}, must provide valid operator {ops.keys()}"
                    )
                if not ops[op](status[key], float(opval)):
                    break
            elif isinstance(status[key], list):
                m = re.match(r"(?P<op>^all|^any|^in)\((?P<value>[\w,]+)\)", value)
                if m is None:
                    raise web.HTTPBadRequest(
                        reason=f"Invalid query for list type: {key}={value}"
                    )
                op = m.group("op")
                opval = m.group("value").split(",")

                # TODO: Implement list operations
                if op == "all":
                    raise web.HTTPBadRequest(
                        reason=f"List operation {op} not implemented."
                    )
                elif op == "any":
                    raise web.HTTPBadRequest(
                        reason=f"List operation {op} not implemented."
                    )
                elif op == "in":
                    raise web.HTTPBadRequest(
                        reason=f"List operation {op} not implemented."
                    )

        else:
            torrents.append(status["info_hash"])

    return torrents


@routes.get("/torrent")
@routes.get("/torrent/{tid}")
async def get_torrent(request):
    core = request.app["spritzle.core"]
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
    core = request.app["spritzle.core"]
    config = request.app["spritzle.config"]

    atp = {"save_path": config.get("add_torrent_params.save_path", "")}

    try:
        post = await request.json()
    except JSONDecodeError as ex:
        raise web.HTTPBadRequest(reason="Invalid JSON", text=ex.msg)

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
        async with aiohttp.ClientSession() as client:
            async with client.get(post.pop("url")) as resp:
                generate_torrent_info(await resp.read())

    elif "info_hash" in post:
        atp["info_hash"] = binascii.unhexlify(post.pop("info_hash"))

    if "ti" in atp:
        info_hash = str(atp["ti"].info_hash())
    elif "info_hash" in atp:
        info_hash = binascii.hexlify(atp["info_hash"]).decode()

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
    core = request.app["spritzle.core"]
    tid = request.match_info.get("tid")
    flag = request.match_info.get("flag", None)
    handle = get_valid_handle(core, tid)

    body = await request.json()

    if flag:
        body = {flag: body}

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
    core = request.app["spritzle.core"]
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
    core = request.app["spritzle.core"]
    tid = request.match_info.get("tid", None)

    # see libtorrent.options_t for valid options
    options = 0

    for key in request.query:
        try:
            options = options | getattr(lt.options_t, key)
        except AttributeError:
            log.warning(f"Invalid option key: {key}")

    if tid is None:
        # If tid is None, we remove all the torrents
        tids = get_torrent_list(core)
    else:
        tids = [tid]

    for tid in tids:
        handle = get_valid_handle(core, tid)
        try:
            await core.torrent.remove(handle, options)
        except AlertException:
            log.error(f"Error deleting files for {handle.name()}")
        core.resume_data.delete(tid)
        del core.torrent_data[tid]

    return web.Response()


@routes.post("/torrent/{tid}/{method}")
async def post_torrent_method(request):

    core = request.app["spritzle.core"]
    tid = request.match_info.get("tid")
    method_name = request.match_info.get("method")
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
