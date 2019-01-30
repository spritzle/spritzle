#
# test_alert.py
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

import asyncio
from unittest.mock import MagicMock

import asynctest
import pytest

import spritzle.alert


class CategoryT:
    test_category1 = 1
    test_category2 = 2
    all_categories = 268435455


class AlertTest:

    def what(self):
        return self.__class__.__name__

    def category(self):
        return 1


class AlertTestOne(AlertTest):
    pass


class AlertTestTwo(AlertTest):

    def category(self):
        return 2


async def test_alert_stop():
    a = spritzle.alert.Alert()
    assert not a.run
    await a.start(MagicMock())
    await asyncio.sleep(0)
    assert a.run
    await a.stop()
    assert not a.run


async def test_pop_alerts(monkeypatch):
    session = MagicMock()

    alert_test_one = AlertTestOne()
    alert_test_two = AlertTestTwo()

    session.configure_mock(**{
        'pop_alerts.return_value': [alert_test_one, alert_test_two],
    })

    monkeypatch.setattr('libtorrent.alert.category_t', CategoryT)
    a = spritzle.alert.Alert()
    a.alert_types = ['AlertTestOne', 'AlertTestTwo', 'AlertTestThree']

    handler_one = asynctest.CoroutineMock()
    a.register_handler('AlertTestOne', handler_one)
    assert 'AlertTestOne' in a.handlers

    handler_two = asynctest.CoroutineMock()
    a.register_handler('AlertTestTwo', handler_two)
    assert 'AlertTestTwo' in a.handlers

    handler_three = asynctest.CoroutineMock()
    a.register_handler('test_category1', handler_three)
    assert 'test_category1' in a.handlers

    await a.start(session)
    a.event.set()
    # Make sure the event.set() has woken up pop_alerts() before stopping.
    await asyncio.sleep(0)
    await a.stop()

    handler_one.assert_called_with(alert_test_one)
    handler_two.assert_called_with(alert_test_two)
    handler_three.assert_called_with(alert_test_one)


async def test_handler_validation():
    async def valid_handler(alert):
        pass

    def invalid_handler(alert):
        pass

    a = spritzle.alert.Alert()
    valid_alert_type = 'torrent_paused_alert'
    valid_category = 'storage_notification'
    invalid_alert_type = 'invalid_alert_type'

    # Verify a valid handler doesn't raise anything
    a.register_handler(valid_alert_type, valid_handler)
    a.register_handler(valid_category, valid_handler)

    with pytest.raises(ValueError):
        a.register_handler(valid_alert_type, invalid_handler)

    with pytest.raises(ValueError):
        a.register_handler(invalid_alert_type, valid_handler)
