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
import logging

import libtorrent as lt

log = logging.getLogger('spritzle')


async def debug_handler(alert):
    if type(alert).__name__ not in ['stats_alert']:
        log.debug(f'{type(alert).__name__} {alert}')


def build_categories():
    # Creates a mapping of category -> int which is used for category alert
    # handlers.
    categories = {}
    for c in dir(lt.alert.category_t):
        if not c.startswith('__'):
            categories[c] = getattr(lt.alert.category_t, c)
    return categories


def build_alert_types():
    """
    Creates a list of valid alert names.
    """
    alerts = []
    for name in dir(lt):
        val = getattr(lt, name)
        if val is lt.alert:
            continue
        if not isinstance(val, type):
            continue
        if not issubclass(val, lt.alert):
            continue
        alerts.append(name)
    return alerts


class Alert(object):

    def __init__(self):
        self.session = None
        self.loop = asyncio.get_event_loop()
        self.pop_alerts_task = None
        self.handlers = {
            'all_categories': [debug_handler],
        }
        self.categories = build_categories()
        self.alert_types = build_alert_types()
        self.run = True

    async def start(self, session):
        log.debug('Alert starting..')
        self.session = session
        self.run = True
        self.pop_alerts_task = self.loop.create_task(self.pop_alerts())

    async def stop(self):
        log.debug('Alert stopping..')
        self.run = False
        if self.pop_alerts_task:
            await self.pop_alerts_task
        log.debug('Alert stopped.')

    def register_handler(self, alert_type, handler):
        if alert_type not in self.alert_types and alert_type not in self.categories:
            raise ValueError('Not a valid alert type or category.')
        if not asyncio.iscoroutinefunction(handler):
            raise ValueError('Alert handlers must by coroutine functions.')
        self.handlers.setdefault(alert_type, []).append(handler)

    async def pop_alerts(self, run_once=False):
        while self.run or run_once:
            if await self.loop.run_in_executor(
                    None, functools.partial(self.session.wait_for_alert), 200):
                if not (self.run or run_once):
                    break

                tasks = []
                for alert in self.session.pop_alerts():
                    handlers = set()
                    handlers.update(self.handlers.get(alert.what(), []))

                    for k, v in self.categories.items():
                        if alert.category() & v:
                            handlers.update(self.handlers.get(k, []))
                    for handler in handlers:
                        tasks.append(self.loop.create_task(handler(alert)))

                # We have to make sure all alert handlers have completed before
                # calling pop_alerts() again as it will invalidate all previous
                # libtorrent alert objects.
                await asyncio.gather(*tasks)

            if run_once:
                break
