#
# spritzle/torrent.py
#
# Copyright (C) 2011 Andrew Resch <andrewresch@gmail.com>
#               2011 Damien Churchill <damoxc@gmail.com>
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

from spritzle.rest import delete, get, post, put
from spritzle.core import core
import spritzle.common as common

import libtorrent as lt
import bottle


@get('/torrent/<tid>')
def get_torrent(tid=None):
    if tid is None:
        return [str(th.info_hash()) for th in core.session.get_torrents()]
    else:
        # TODO: get torrent status
        return {}

@post('/torrent')
def add_torrent():
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

    print(len(bottle.request.files))
    for key, value in bottle.request.files.items():

        data = value.file.read()
        atp['ti'] = lt.torrent_info(lt.bdecode(data))
        # TODO: add support for adding multiple files at once
        break

    for key, value in bottle.request.forms.items():
        if key == 'ti':
            # Ignore ti because it can't be useful
            continue
        atp[key] = value

    if len(set(atp.keys()).intersection(('ti', 'url', 'info_hash'))) != 1:
        # We require that only one of ti, url or info_hash is set
        bottle.abort(400, "Only one of 'ti', 'url' or 'info_hash' allowed.")

    try:
        th = core.session.add_torrent(atp)
    except RuntimeError as e:
        bottle.abort(400, str(e))

    return str(th.info_hash())