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
import functools
import binascii
import json

from aiohttp import web
from aiohttp.errors import HttpProcessingError

from spritzle.core import core
import spritzle.common as common

import libtorrent as lt


def get_valid_handle(tid):
    """
    Either returns a valid torrent_handle or aborts with a client-error (400)
    """
    handle = core.session.find_torrent(lt.sha1_hash(binascii.unhexlify(tid)))
    if not handle.is_valid():
        raise HttpProcessingError(
            code=404, message='Torrent not found: ' + tid)

    return handle


def get_torrent_list():
    return [str(th.info_hash()) for th in core.session.get_torrents()]

async def get_torrent(request):
    tid = request.match_info.get('tid', None)

    if tid is None:
        return web.json_response(get_torrent_list())
    else:
        handle = get_valid_handle(tid)

        # We don't want to return all of the keys as they are just an enum
        ignored = ['states'] + list(lt.torrent_status.states.names.keys())

        status = common.struct_to_dict(
            handle.status(),
            ignore_keys=ignored,
        )

        return web.json_response(status)

async def post_torrent(request):
    """
    libtorrent requires one of these three fields: ti, url, info_hash
    The save_path field is always required.

    Since the ti field isn't feasible to use over rpc we will ignore it.
    Instead, we will look for any uploaded files in the POST and create
    the torrent_info object based on the file data.

    http://libtorrent.org/reference-Session.html#add_torrent_params
    """

    atp = {
        'save_path': core.config.get('add_torrent_params.save_path', '')
    }

    post = await request.post()

    if 'file' in post:
        data = post['file'].file.read()

        try:
            atp['ti'] = lt.torrent_info(lt.bdecode(data))
        except RuntimeError as e:
            raise HttpProcessingError(
                code=400, message='Not a valid torrent file!')

    if 'args' in post:
        args = json.loads(post['args'])
        for key, value in args.items():
            if key == 'ti':
                # Ignore ti because it can't be useful
                continue
            atp[key] = value

    if len(set(atp.keys()).intersection(('ti', 'url', 'info_hash'))) != 1:
        # We require that only one of ti, url or info_hash is set
        raise HttpProcessingError(
            code=400,
            message="Only one of 'ti', 'url' or 'info_hash' allowed."
        )

    try:
        th = await asyncio.get_event_loop().run_in_executor(
                None, functools.partial(core.session.add_torrent), atp)
    except RuntimeError as e:
        raise HttpProcessingError(
            code=500, message="Error in session.add_torrent(): " + str(e))

    info_hash = str(th.info_hash())

    return web.json_response(
        {'info_hash': info_hash},
        status=201,
        headers={'Location': '{}://{}/torrent/{}'.format(
            request.scheme, request.host, info_hash)}
        )

async def delete_torrent(request):
    tid = request.match_info.get('tid', None)

    # see libtorrent.options_t for valid options
    options = 0

    for key in request.GET.keys():
        options = options | lt.options_t.names[key]

    if tid is None:
        # If tid is None, we remove all the torrents
        tids = get_torrent_list()
    else:
        tids = [tid]

    for tid in tids:
        handle = get_valid_handle(tid)
        core.session.remove_torrent(handle, options)

    return web.Response()
