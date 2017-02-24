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

import os
import json

from unittest.mock import patch, MagicMock
from nose.tools import assert_raises

import aiohttp.web
from aiohttp.web_reqrep import FileField

from spritzle.resource import torrent
from spritzle.tests.common import run_until_complete, json_response
import spritzle.tests.common

torrent_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'torrents')


def create_mock_request(filename=None, url=None, info_hash=None, args=None):
    async def post():
        post = {}
        a = {
            'ti': None,
            'paused': True,
        }
        if args:
            a.update(args)

        post['args'] = json.dumps(a)

        if filename:
            filepath = os.path.join(torrent_dir, filename)
            f = FileField("file", filename, open(filepath, 'rb'), 'text/plain')
            post['file'] = f

        if url:
            post['url'] = url

        if info_hash:
            post['info_hash'] = info_hash

        return post

    request = spritzle.tests.common.create_mock_request()
    request.post = post
    request.scheme = 'http'
    request.host = 'localhost:8080'

    return request


@run_until_complete
async def test_get_torrent():
    request = await test_post_torrent()

    request.match_info = {}

    torrents, response = await json_response(torrent.get_torrent(request))
    assert isinstance(torrents, list)
    assert len(torrents) > 0

    request.match_info['tid'] = '44a040be6d74d8d290cd20128788864cbf770719'

    ts, response = await json_response(torrent.get_torrent(request))
    assert isinstance(ts, dict)
    assert ts['info_hash'] == '44a040be6d74d8d290cd20128788864cbf770719'

    with assert_raises(aiohttp.web.HTTPNotFound):
        request.match_info['tid'] = 'a0'*20
        _, response = await torrent.get_torrent(request)
        assert response.status == 404


@run_until_complete
async def test_post_torrent():
    request = create_mock_request(filename='random_one_file.torrent')

    body, response = await json_response(torrent.post_torrent(request))
    assert 'info_hash' in body
    info_hash = body['info_hash']

    assert response.headers['LOCATION'] == \
        'http://localhost:8080/torrent/{}'.format(info_hash)
    assert response.status == 201

    assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'

    request.match_info = {}
    tlist, response = await json_response(torrent.get_torrent(request))
    assert tlist == ['44a040be6d74d8d290cd20128788864cbf770719']
    return request


@run_until_complete
async def test_post_torrent_bad_body():
    request = create_mock_request(filename='random_one_file.torrent')

    async def json():
        return b'\xc3\x28'.decode("utf8")

    request.json = json
    body, response = await json_response(torrent.post_torrent(request))
    assert 'info_hash' in body

    info_hash = body['info_hash']

    assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'


@run_until_complete
async def test_post_torrent_info_hash():
    request = create_mock_request(
        info_hash='44a040be6d74d8d290cd20128788864cbf770719')

    body, response = await json_response(torrent.post_torrent(request))
    assert 'info_hash' in body
    info_hash = body['info_hash']
    assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'


@run_until_complete
async def test_add_torrent_lt_runtime_error():
    request = create_mock_request(filename='random_one_file.torrent')

    add_torrent = MagicMock()
    add_torrent.side_effect = RuntimeError()
    request.app['spritzle.core'].session.add_torrent = add_torrent
    with assert_raises(aiohttp.web.HTTPInternalServerError):
        _, response = await json_response(torrent.post_torrent(request))
        assert response.status == 500


@run_until_complete
async def test_add_torrent_bad_file():
    request = create_mock_request('empty.torrent')

    with assert_raises(aiohttp.web.HTTPBadRequest):
        _, response = await json_response(torrent.post_torrent(request))
        assert response.status == 400


@run_until_complete
async def test_add_torrent_bad_number_args():
    request = create_mock_request(
        url='http://testing/test.torrent',
        info_hash='a0'*20)

    with assert_raises(aiohttp.web.HTTPBadRequest):
        _, response = await json_response(torrent.post_torrent(request))
        assert response.status == 400


@run_until_complete
async def test_add_torrent_url():
    request = create_mock_request(url='http://localhost/test.torrent')
    data = open(
        os.path.join(torrent_dir, 'random_one_file.torrent'), 'rb').read()

    class AsyncContextManager:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return

        async def read(self):
            return data

    class ClientSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return

        def get(self, url):
            return AsyncContextManager()

    with patch('aiohttp.ClientSession', new=ClientSession):
        body, response = await json_response(torrent.post_torrent(request))
        assert response.status == 201


@run_until_complete
async def test_remove_torrent():
    request = await test_post_torrent()
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
async def test_remove_torrent_all():
    await test_post_torrent()

    request = create_mock_request()
    request.match_info = {}
    request.GET = {
        'delete_files': True,
    }

    response = await torrent.delete_torrent(request)
    assert response.status == 200
    core = request.app['spritzle.core']
    assert len(torrent.get_torrent_list(core)) == 0
