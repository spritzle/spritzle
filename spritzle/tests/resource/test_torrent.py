#
# test_torrent.py
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
#

from base64 import b64encode
import json
from pathlib import Path
from unittest.mock import MagicMock

import libtorrent as lt
import aiohttp.web

from spritzle.resource import torrent

torrent_dir = Path(Path(__file__).resolve().parent, 'torrents')


def create_torrent_post_data(filename=None, **kwargs):
    data = {'flags': lt.torrent_flags.paused}
    data.update(kwargs)
    if filename:
        filepath = Path(torrent_dir, filename)
        data['file'] = b64encode(filepath.open(mode='rb').read()).decode('ascii')

    return data


async def test_get_torrent(cli):
    await test_post_torrent(cli)

    response = await cli.get('/torrent')
    torrents = await response.json()
    assert isinstance(torrents, list)
    assert len(torrents) > 0

    info_hash = '44a040be6d74d8d290cd20128788864cbf770719'

    response = await cli.get(f'/torrent/{info_hash}')
    ts = await response.json()
    assert isinstance(ts, dict)
    assert ts['info_hash'] == info_hash
    assert ts['spritzle.tags'] == ['foo']

    response = await cli.get('/torrent/' + 'a0'*20)
    assert response.status == 404


async def test_post_torrent(cli):
    post_data = create_torrent_post_data(filename='random_one_file.torrent',
                                        tags=['foo'])
    response = await cli.post('/torrent', json=post_data)
    body = await response.json()
    assert 'info_hash' in body
    info_hash = body['info_hash']

    assert response.headers['LOCATION'] == \
        f'http://localhost:8080/torrent/{info_hash}'
    assert response.status == 201

    assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'

    response = await cli.get('/torrent')
    tlist = await response.json()
    assert tlist == ['44a040be6d74d8d290cd20128788864cbf770719']


async def test_post_torrent_info_hash(cli):
    post_data = create_torrent_post_data(
        info_hash='44a040be6d74d8d290cd20128788864cbf770719')

    response = await cli.post('/torrent', json=post_data)
    body = await response.json()
    assert 'info_hash' in body
    info_hash = body['info_hash']
    assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'


async def test_add_torrent_form_encoding(core, cli):
    filepath = Path(torrent_dir, 'random_one_file.torrent')
    post_data = [('file', filepath.open(mode='rb')),
              ('tags', 'tag1'),
              ('tags', 'tag2')]

    response = await cli.post('/torrent', data=post_data)
    body = await response.json()
    assert 'info_hash' in body
    info_hash = body['info_hash']

    assert response.headers['LOCATION'] == \
        f'http://localhost:8080/torrent/{info_hash}'
    assert response.status == 201

    assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'

    response = await cli.get('/torrent')
    tlist = await response.json()
    assert tlist == ['44a040be6d74d8d290cd20128788864cbf770719']

    assert core.torrent_data[info_hash]['spritzle.tags'] == ['tag1', 'tag2']


async def test_add_torrent_lt_runtime_error(cli, core):
    post_data = create_torrent_post_data(filename='random_one_file.torrent')

    add_torrent = MagicMock()
    add_torrent.side_effect = RuntimeError()
    core.session.add_torrent = add_torrent
    response = await cli.post('/torrent', json=post_data)
    assert response.status == 500


async def test_add_torrent_bad_file(cli):
    post_data = create_torrent_post_data(filename='empty.torrent')

    response = await cli.post('/torrent', json=post_data)
    assert response.status == 400


async def test_add_torrent_bad_number_args(cli):
    post_data = create_torrent_post_data(
        url='http://testing/test.torrent',
        info_hash='a0'*20)

    response = await cli.post('/torrent', json=post_data)
    assert response.status == 400


async def test_add_torrent_bad_args(cli):
    post_data = create_torrent_post_data(
        filename='random_one_file.torrent',
        bad_key=True,
    )

    response = await cli.post('/torrent', json=post_data)
    assert response.status == 400


async def test_add_torrent_url(app, aiohttp_client):
    async def get_test_torrent(request):
        return aiohttp.web.FileResponse(
            Path(torrent_dir, 'random_one_file.torrent'))

    app.router.add_route('GET', '/test.torrent', get_test_torrent)
    cli = await aiohttp_client(app)
    torrent_address = str(cli.make_url('/test.torrent'))

    post_data = create_torrent_post_data(url=torrent_address)

    response = await cli.post('/torrent', json=post_data)
    assert response.status == 201


async def test_remove_torrent(cli):
    await test_post_torrent(cli)
    tid = '44a040be6d74d8d290cd20128788864cbf770719'

    response = await cli.delete(f'/torrent/{tid}',
                                params={'delete_files': 1})
    assert response.status == 200

    response = await cli.get('/torrent')
    torrents = await response.json()
    assert response.status == 200
    assert len(torrents) == 0


async def test_remove_torrent_all(cli, core):
    await test_post_torrent(cli)

    response = await cli.delete('/torrent', params={'delete_files': 1})
    assert response.status == 200
    assert len(torrent.get_torrent_list(core)) == 0
