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

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

import libtorrent as lt
import aiohttp.web
from aiohttp.web import FileField

from spritzle.resource import torrent
from spritzle.tests.common import run_until_complete, json_response
import spritzle.tests.common

torrent_dir = Path(Path(__file__).resolve().parent, 'torrents')


async def create_mock_request(core=None, filename=None, url=None,
                              info_hash=None, args=None, tags=None):
    async def post():
        post = {}
        a = {
            'ti': None,
            'flags': lt.torrent_flags.paused,
        }
        if args:
            a.update(args)

        post['args'] = json.dumps(a)

        if filename:
            filepath = Path(torrent_dir, filename)
            f = FileField(
                'file', filename, filepath.open(mode='rb'), 'text/plain', {})
            post['file'] = f

        if url:
            post['url'] = url

        if info_hash:
            post['info_hash'] = info_hash

        if tags:
            post['tags'] = json.dumps(tags)

        return post

    request = await spritzle.tests.common.create_mock_request(core=core)
    request.post = post
    request.scheme = 'http'
    request.host = 'localhost:8080'

    return request


@run_until_complete
async def test_get_torrent(core):
    request = await test_post_torrent(core)

    request.match_info = {}

    torrents, response = await json_response(torrent.get_torrent(request))
    assert isinstance(torrents, list)
    assert len(torrents) > 0

    request.match_info['tid'] = '44a040be6d74d8d290cd20128788864cbf770719'

    ts, response = await json_response(torrent.get_torrent(request))
    assert isinstance(ts, dict)
    assert ts['info_hash'] == '44a040be6d74d8d290cd20128788864cbf770719'
    assert ts['spritzle.tags'] == ['foo']

    with pytest.raises(aiohttp.web.HTTPNotFound):
        request.match_info['tid'] = 'a0'*20
        _, response = await torrent.get_torrent(request)
        assert response.status == 404


@run_until_complete
async def test_post_torrent(core):
    request = await create_mock_request(core=core,
                                        filename='random_one_file.torrent',
                                        tags=['foo'])

    body, response = await json_response(torrent.post_torrent(request))
    assert 'info_hash' in body
    info_hash = body['info_hash']

    assert response.headers['LOCATION'] == \
        f'http://localhost:8080/torrent/{info_hash}'
    assert response.status == 201

    assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'

    request.match_info = {}
    tlist, response = await json_response(torrent.get_torrent(request))
    assert tlist == ['44a040be6d74d8d290cd20128788864cbf770719']
    return request


@run_until_complete
async def test_post_torrent_info_hash(core):
    request = await create_mock_request(
        core=core,
        info_hash='44a040be6d74d8d290cd20128788864cbf770719')

    body, response = await json_response(torrent.post_torrent(request))
    assert 'info_hash' in body
    info_hash = body['info_hash']
    assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'


@run_until_complete
async def test_add_torrent_lt_runtime_error(core):
    request = await create_mock_request(core=core,
                                        filename='random_one_file.torrent')

    add_torrent = MagicMock()
    add_torrent.side_effect = RuntimeError()
    request.app['spritzle.core'].session.add_torrent = add_torrent
    with pytest.raises(aiohttp.web.HTTPInternalServerError):
        _, response = await json_response(torrent.post_torrent(request))
        assert response.status == 500


@run_until_complete
async def test_add_torrent_bad_file(core):
    request = await create_mock_request(core=core, filename='empty.torrent')

    with pytest.raises(aiohttp.web.HTTPBadRequest):
        _, response = await json_response(torrent.post_torrent(request))
        assert response.status == 400


@run_until_complete
async def test_add_torrent_bad_number_args(core):
    request = await create_mock_request(
        core=core,
        url='http://testing/test.torrent',
        info_hash='a0'*20)

    with pytest.raises(aiohttp.web.HTTPBadRequest):
        _, response = await json_response(torrent.post_torrent(request))
        assert response.status == 400


@run_until_complete
async def test_add_torrent_bad_args(core):
    request = await create_mock_request(
        core=core,
        filename='random_one_file.torrent',
        args={'bad_key': True},
    )

    with pytest.raises(aiohttp.web.HTTPBadRequest):
        _, response = await json_response(torrent.post_torrent(request))
        assert response.status == 400


@run_until_complete
async def test_add_torrent_url(core):
    request = await create_mock_request(
        core=core,
        url='http://localhost/test.torrent')
    data = Path(torrent_dir, 'random_one_file.torrent').read_bytes()

    class AsyncContextManager:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return

        async def read(self):
            return data

    class ClientSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return

        def get(self, url):
            return AsyncContextManager()

    with patch('aiohttp.ClientSession', new=ClientSession):
        body, response = await json_response(torrent.post_torrent(request))
        assert response.status == 201


@run_until_complete
async def test_remove_torrent(core):
    request = await test_post_torrent(core)
    tid = '44a040be6d74d8d290cd20128788864cbf770719'

    request.match_info = {
        'tid': tid
    }
    request.GET = {
        'delete_files': True,
    }

    response = await torrent.delete_torrent(request)
    assert response.status == 200

    request.match_info = {}
    response = await torrent.get_torrent(request)
    assert response.status == 200


@run_until_complete
async def test_remove_torrent_all(core):
    await test_post_torrent(core)

    request = await create_mock_request(core=core)
    request.match_info = {}
    request.GET = {
        'delete_files': True,
    }

    response = await torrent.delete_torrent(request)
    assert response.status == 200
    core = request.app['spritzle.core']
    assert len(torrent.get_torrent_list(core)) == 0
