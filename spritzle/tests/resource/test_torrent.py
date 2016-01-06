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

import libtorrent as lt
import bottle

from spritzle.main import bootstrap
from spritzle.resource import torrent

bootstrap()

def create_files_dict(torrent):
    return {
        torrent: bottle.FileUpload(
            open(os.path.join(torrent_dir, torrent + '.torrent'), 'rb'),
            torrent + '.torrent',
            torrent + '.torrent'
        )
    }

def create_mock_request(files=None, args=None):
    request = MagicMock()
    if files:
        request.files = files
    request.json = {
        'ti': None,
        'paused': True,
    }

    if args:
        request.json.update(args)

    return request

def test_get_torrent():
    test_add_torrent()

    torrents = torrent.get_torrent()
    assert isinstance(torrents, list)
    assert len(torrents) > 0

    ts = torrent.get_torrent('44a040be6d74d8d290cd20128788864cbf770719')
    assert isinstance(ts, dict)
    assert ts['info_hash'] == '44a040be6d74d8d290cd20128788864cbf770719'

    with assert_raises(bottle.HTTPError) as e:
        ts = torrent.get_torrent('a0'*20)

def test_add_torrent():
    files = create_files_dict('random_one_file')
    request = create_mock_request(files=files)

    with patch('bottle.request', request):
        info_hash = torrent.add_torrent()['info_hash']
        assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'
        assert torrent.get_torrent() == ['44a040be6d74d8d290cd20128788864cbf770719']

def test_add_torrent_lt_runtime_error():
    files = create_files_dict('random_one_file')
    request = create_mock_request(files=files)

    add_torrent = MagicMock()
    add_torrent.side_effect = RuntimeError()

    with patch('bottle.request', request):
        with patch('spritzle.core.core.session.add_torrent', add_torrent):
            with assert_raises(bottle.HTTPError) as e:
                info_hash = torrent.add_torrent()['info_hash']
            assert e.exception.status_code == 500

def test_add_torrent_bad_file():
    files = create_files_dict('empty')
    request = create_mock_request(files=files)

    with patch('bottle.request', request):
        with assert_raises(bottle.HTTPError) as e:
            torrent.add_torrent()
        assert e.exception.status_code == 400

def test_add_torrent_bad_args():
    request = create_mock_request(args={
            'url': 'http://testing/test.torrent',
            'info_hash': 'a0'*20,
        })

    with patch('bottle.request', request):
        with assert_raises(bottle.HTTPError) as e:
            torrent.add_torrent()
        assert e.exception.status_code == 400

def test_remove_torrent():
    test_add_torrent()
    tid = '44a040be6d74d8d290cd20128788864cbf770719'

    request = MagicMock()
    request.json = {'delete_files': True}

    with patch('bottle.request', request):
        torrent.remove_torrent(tid)
        assert tid not in torrent.get_torrent()

def test_remove_torrent_all():
    test_add_torrent()

    request = MagicMock()
    request.json = {'delete_files': True}

    with patch('bottle.request', request):
        torrent.remove_torrent()
        assert len(torrent.get_torrent()) == 0