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

from unittest.mock import MagicMock
from collections import namedtuple

import spritzle.alert
from spritzle.tests.common import run_until_complete


class CategoryT:
    values = {
        1: namedtuple('_', 'name')('test_category1'),
        2: namedtuple('_', 'name')('test_category2'),
        268435455: namedtuple('_', 'name')('all_categories'),
    }


class AlertTest:

    def category(self):
        return 1
    category_t = CategoryT


class AlertTestOne(AlertTest):
    pass


class AlertTestTwo(AlertTest):

    def category(self):
        return 2


def test_alert_stop():
    a = spritzle.alert.Alert()
    assert a.run
    a.start(MagicMock())
    a.stop()
    assert not a.run


@run_until_complete
async def test_pop_alerts():
    session = MagicMock()

    alert_test_one = AlertTestOne()
    alert_test_two = AlertTestTwo()

    session.configure_mock(**{
        'wait_for_alert.return_value': True,
        'pop_alerts.return_value': [alert_test_one, alert_test_two],
    })

    a = spritzle.alert.Alert()
    a.session = session

    handler_one = MagicMock()
    a.register_handler('AlertTestOne', handler_one)
    assert 'AlertTestOne' in a.handlers

    handler_two = MagicMock()
    a.register_handler('AlertTestTwo', handler_two)
    assert 'AlertTestTwo' in a.handlers

    handler_three = MagicMock()
    a.register_handler('test_category1', handler_three)
    assert 'test_category1' in a.handlers

    await a.pop_alerts(run_once=True)

    handler_one.assert_called_with(alert_test_one)
    handler_two.assert_called_with(alert_test_two)
    handler_three.assert_called_with(alert_test_one)
