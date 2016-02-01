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
torrent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'torrents')
from unittest.mock import patch, MagicMock
from nose.tools import assert_raises

import aiohttp.web_reqrep
import aiohttp.errors
import libtorrent as lt
import asyncio
import io

from spritzle.resource import torrent
from spritzle.tests.common import run_until_complete, json_response
import spritzle.tests.common as common
from spritzle.main import bootstrap

bootstrap()

loop = asyncio.get_event_loop()

def create_mock_request(filename=None, args=None):
    request = MagicMock()

    async def json():
        d = {
            'ti': None,
            'paused': True,
        }
        if args:
            d.update(args)
        return d

    async def post():
        if filename:
            filepath = os.path.join(torrent_dir, filename)
            f = aiohttp.web_reqrep.FileField("file", filename, open(filepath, 'rb'), 'text/plain')
            return {'file': f}
        else:
            return {}

    request = MagicMock()
    request.json = json
    request.post = post

    return request

@run_until_complete
async def test_get_torrent():
    await test_post_torrent()

    request = MagicMock()
    request.match_info = {}

    torrents = await json_response(torrent.get_torrent(request))
    assert isinstance(torrents, list)
    assert len(torrents) > 0

    request.match_info['tid'] = '44a040be6d74d8d290cd20128788864cbf770719'

    ts = await json_response(torrent.get_torrent(request))
    assert isinstance(ts, dict)
    assert ts['info_hash'] == '44a040be6d74d8d290cd20128788864cbf770719'

    with assert_raises(aiohttp.errors.HttpProcessingError) as e:
        request.match_info['tid'] = 'a0'*20
        ts = await json_response(torrent.get_torrent(request))

@run_until_complete
async def test_post_torrent():
    request = create_mock_request(filename='random_one_file.torrent')

    response = await json_response(torrent.post_torrent(request))
    assert 'info_hash' in response

    info_hash = response['info_hash']

    assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'

    request = MagicMock()
    request.match_info = {}
    tlist = await json_response(torrent.get_torrent(request))
    assert tlist == ['44a040be6d74d8d290cd20128788864cbf770719']

@run_until_complete
async def test_add_torrent_lt_runtime_error():
    request = create_mock_request(filename='random_one_file.torrent')

    add_torrent = MagicMock()
    add_torrent.side_effect = RuntimeError()

    with patch('spritzle.core.core.session.add_torrent', add_torrent):
        with assert_raises(aiohttp.errors.HttpProcessingError) as e:
            response = await json_response(torrent.post_torrent(request))
            assert e.exception.code == 500

@run_until_complete
async def test_add_torrent_bad_file():
    request = create_mock_request('empty.torrent')

    with assert_raises(aiohttp.errors.HttpProcessingError) as e:
        await json_response(torrent.post_torrent(request))
    assert e.exception.code == 400

@run_until_complete
async def test_add_torrent_bad_args():
    request = create_mock_request(args={
            'url': 'http://testing/test.torrent',
            'info_hash': 'a0'*20,
        })

    with assert_raises(aiohttp.errors.HttpProcessingError) as e:
        await json_response(torrent.post_torrent(request))
    assert e.exception.code == 400

@run_until_complete
async def test_remove_torrent():
    await test_post_torrent()
    tid = '44a040be6d74d8d290cd20128788864cbf770719'

    async def json():
        return {'delete_files': True}

    request = MagicMock()
    request.match_info = {
        'tid': tid
    }
    request.json = json

    await json_response(torrent.delete_torrent(request))
    request = MagicMock()
    request.match_info = {}

    assert tid not in await json_response(torrent.get_torrent(request))

@run_until_complete
async def test_remove_torrent_all():
    await test_post_torrent()

    async def json():
        return {'delete_files': True}

    request = MagicMock()
    request.json = json
    request.match_info = {}

    await json_response(torrent.delete_torrent(request))
    assert len(torrent.get_torrent_list()) == 0