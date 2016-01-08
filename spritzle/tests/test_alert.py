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

from unittest.mock import patch, MagicMock
import spritzle.alert

class AlertTestOne(object):
    pass

class AlertTestTwo(object):
    pass

def test_pop_alerts():
    loop = MagicMock()
    asyncio = MagicMock()
    asyncio.configure_mock(**{
        'get_event_loop.return_value': loop,
    })

    spritzle.alert.asyncio = asyncio
    session = MagicMock()
    
    alert_test_one = AlertTestOne()
    alert_test_two = AlertTestTwo()

    session.configure_mock(**{
        'wait_for_alert.return_value': True,
        'pop_alerts.return_value': [alert_test_one, alert_test_two],
    })
    
    a = spritzle.alert.Alert(session)
    loop.call_soon.assert_called_with(a.pop_alerts)
    loop.reset_mock()

    handler_one = MagicMock()
    a.register_handler('AlertTestOne', handler_one)
    assert 'AlertTestOne' in a.handlers

    handler_two = MagicMock()
    a.register_handler('AlertTestTwo', handler_two)
    assert 'AlertTestTwo' in a.handlers
    
    a.pop_alerts()

    handler_one.assert_called_with(alert_test_one)
    handler_two.assert_called_with(alert_test_two)

    loop.call_later.assert_called_with(a.pop_alerts)

