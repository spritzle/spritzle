#
# test_aiohttp.py
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

from unittest.mock import patch, MagicMock
import asyncio
import os
import signal

from spritzle.aiohttp import AiohttpServer

def test_aiohttp_run():
    def handler(*args, **kwargs):
        pass

    with patch('asyncio.get_event_loop'):
        a = AiohttpServer()
        a.run(handler)
        asyncio.get_event_loop.assert_called_once_with()

def test_aiohttp_stop():
    a = AiohttpServer()
    a.loop.stop = MagicMock(name='stop')
    a.stop()
    assert a.loop.stop.called

def test_aiohttp_run_bottle_child():
    def handler(*args, **kwargs):
        pass

    os.environ['BOTTLE_CHILD'] = ''
    with patch('asyncio.get_event_loop'):
        with patch('signal.signal'):
            a = AiohttpServer()
            a.run(handler)
            signal.signal.assert_called_once_with(signal.SIGINT, a.stop)