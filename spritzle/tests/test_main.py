#
# test_main.py
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
from nose.tools import assert_raises

import spritzle.main

def test_main_class():
    main = spritzle.main.Main(12345)
    assert main.port == 12345

    with patch('spritzle.main.bottle.run'):
        main.start()
        spritzle.main.bottle.run.assert_called_once_with(
            port=12345,
            reloader=False,
            debug=False,
            server=spritzle.main.AiohttpServer
        )

def test_main_entry_point():
    with patch('spritzle.main.Main.start'):
        with patch('sys.argv'):
        
            spritzle.main.main()
            spritzle.main.Main.start.assert_called_once_with()
