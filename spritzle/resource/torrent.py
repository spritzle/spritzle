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
import logging

import aiohttp
from aiohttp import web

import spritzle.common as common

import libtorrent as lt

log = logging.getLogger('spritzle')


def get_valid_handle(core, tid):
    """
    Either returns a valid torrent_handle or aborts with a client-error (400)
    """
    handle = core.session.find_torrent(lt.sha1_hash(binascii.unhexlify(tid)))
    if not handle.is_valid():
        raise web.HTTPNotFound(reason='Torrent not found: ' + tid)

    return handle


def get_torrent_list(core):
    return [str(th.info_hash()) for th in core.session.get_torrents()]


async def get_torrent(request):
    core = request.app['spritzle.core']
    tid = request.match_info.get('tid', None)

    if tid is None:
        return web.json_response(get_torrent_list(core))
    else:
        handle = get_valid_handle(core, tid)

        # We don't want to return all of the keys as they are just an enum
        ignored = (['states', 'handle', 'torrent_file'] +
                   list(lt.torrent_status.states.names.keys()))

        status = common.struct_to_dict(
            handle.status(),
            ignore_keys=ignored,
        )

        if tid in core.torrent_data:
            status.update(core.torrent_data[tid])

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
    core = request.app['spritzle.core']
    config = request.app['spritzle.config']

    atp = {
        'save_path': config.get('add_torrent_params.save_path', '')
    }

    post = await request.post()

    if 'args' in post:
        args = json.loads(post['args'])
        for key, value in args.items():
            if key in ('ti', 'info_hash'):
                continue
            atp[key] = value

    # We require that only one of file, url or info_hash is set
    if len(set([*post.keys()]).intersection(
            ('file', 'url', 'info_hash'))) != 1:
        raise web.HTTPBadRequest(
            reason="One of and only one 'file', 'url' or 'info_hash' allowed."
        )

    def generate_torrent_info(data):
        try:
            atp['ti'] = lt.torrent_info(lt.bdecode(data))
        except RuntimeError as e:
            raise web.HTTPBadRequest(
                reason=f'Not a valid torrent file: {e}')

    if 'file' in post:
        generate_torrent_info(post['file'].file.read())
    # We do not use libtorrent's ability to download torrents as it will
    # probably be removed in future versions and cannot provide the
    # info-hash when we need it.
    # See: https://github.com/arvidn/libtorrent/issues/481
    elif 'url' in post:
        async with aiohttp.ClientSession() as client:
            async with client.get(post['url']) as resp:
                generate_torrent_info(await resp.read())

    elif 'info_hash' in post:
        atp['info_hash'] = binascii.unhexlify(post['info_hash'])

    if 'ti' in atp:
        info_hash = str(atp['ti'].info_hash())
    elif 'info_hash' in atp:
        info_hash = binascii.hexlify(atp['info_hash']).decode()

    if info_hash not in core.torrent_data:
        core.torrent_data[info_hash] = {}

    if 'tags' in post:
        tags = json.loads(post['tags'])
        core.torrent_data[info_hash]['spritzle.tags'] = tags

    try:
        await asyncio.get_event_loop().run_in_executor(
                None, functools.partial(core.session.add_torrent), atp)
    except KeyError as e:
        raise web.HTTPBadRequest(
            reason=str(e))
    except RuntimeError as e:
        raise web.HTTPInternalServerError(
            reason=f'Error in session.add_torrent(): {e}')

    return web.json_response(
        {'info_hash': info_hash},
        status=201,
        headers={'Location': f'{request.scheme}://{request.host}/torrent/{info_hash}'}
        )


async def delete_torrent(request):
    core = request.app['spritzle.core']
    tid = request.match_info.get('tid', None)

    # see libtorrent.options_t for valid options
    options = 0

    for key in request.GET.keys():
        try:
            options = options | getattr(lt.options_t, key)
        except AttributeError as e:
            log.warning(f'Invalid option key: {key}')

    if tid is None:
        # If tid is None, we remove all the torrents
        tids = get_torrent_list(core)
    else:
        tids = [tid]

    for tid in tids:
        handle = get_valid_handle(core, tid)
        core.session.remove_torrent(handle, options)

    return web.Response()
