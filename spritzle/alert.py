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
import functools


def debug_handler(alert):
    print('alert: {}'.format(type(alert).__name__))


class Alert(object):
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.handlers = {
            '*': [],
        }
        self.run = True
        self.register_handler('*', debug_handler)

    def start(self, session):
        self.session = session
        self.run = True
        asyncio.ensure_future(self.pop_alerts())

    def stop(self):
        self.run = False

    def register_handler(self, alert_type, handler):
        if alert_type not in self.handlers:
            self.handlers[alert_type] = []

        self.handlers[alert_type].append(handler)

    async def pop_alerts(self, run_once=False):
        while self.run or run_once:
            if await self.loop.run_in_executor(
                    None, functools.partial(self.session.wait_for_alert), 200):
                for alert in self.session.pop_alerts():
                    alert_type = type(alert).__name__

                    handlers = set(
                        self.handlers.get(alert_type, []) +
                        self.handlers['*'])

                    for handler in handlers:
                        handler(alert)

            if run_once:
                break