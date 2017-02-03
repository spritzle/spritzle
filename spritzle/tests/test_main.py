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

import spritzle.main


def test_main_start():
    main = spritzle.main.Main(12345)
    assert main.port == 12345
    main.loop = MagicMock()
    with patch('spritzle.main.core') as core:
        with patch('aiohttp.web.run_app') as run_app:
            main.start()
            run_app.assert_called_once_with(spritzle.main.app)
        assert core.init.called
    assert main.loop.add_signal_handler.called


def test_main_stop():
    # pylint: disable=E1101
    main = spritzle.main.Main(12345)
    main.executor = MagicMock()
    main.loop = MagicMock()
    with patch('spritzle.main.core') as core:
        main.stop()
        assert core.stop.called
    assert main.loop.stop.called
    assert main.executor.shutdown.called


def test_main_entry_point():
    # pylint: disable=E1101
    with patch('spritzle.main.Main.start'):
        with patch('sys.argv', ['']):
            spritzle.main.main()
            spritzle.main.Main.start.assert_called_once_with()
