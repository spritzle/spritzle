#
# spritzle/alert.py
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

import libtorrent as lt

class Alert(object):
    def __init__(self, session):
        self.loop = asyncio.get_event_loop()

        self.session = session
        self.session.set_alert_mask(
            lt.alert.category_t.all_categories)

        self.handlers = {}

        self.loop.call_soon(self.pop_alerts)

    def register_handler(self, alert_type, handler):
        if alert_type not in self.handlers:
            self.handlers[alert_type] = []

        self.handlers[alert_type].append(handler)

    def pop_alerts(self):
        if self.session.wait_for_alert(5000):
            for alert in self.session.pop_alerts():
                alert_type = type(alert).__name__

                if alert_type in self.handlers:
                    for handler in self.handlers[alert_type]:
                        handler(alert)

        self.loop.call_later(self.pop_alerts)