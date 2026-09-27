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
import inspect
import logging
import socket
from typing import Optional

import libtorrent as lt

log = logging.getLogger("spritzle")


async def debug_handler(alert):
    if type(alert).__name__ not in ["stats_alert"]:
        log.debug(f"{type(alert).__name__} {alert}")


def build_categories():
    # Creates a mapping of category -> int which is used for category alert
    # handlers.
    categories = {}
    for c in dir(lt.alert.category_t):
        if not c.startswith("__"):
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
        self.session: Optional[lt.session] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.pop_alerts_task = None
        self.run = False
        self.event = asyncio.Event()
        self.handlers = {"all_categories": [debug_handler]}
        self.categories = build_categories()
        self.alert_types = build_alert_types()
        self._notify_r: Optional[socket.socket] = None
        self._notify_w: Optional[socket.socket] = None

    def __del__(self):
        r = getattr(self, "_notify_r", None)
        if r is not None:
            try:
                r.close()
            except Exception:
                pass
            self._notify_r = None
        w = getattr(self, "_notify_w", None)
        if w is not None:
            try:
                w.close()
            except Exception:
                pass
            self._notify_w = None


    async def start(self, session):
        self.loop = asyncio.get_running_loop()
        log.debug("Alert starting..")
        self.session = session
        self.run = True
        self.pop_alerts_task = self.loop.create_task(self.pop_alerts())

        # libtorrent's set_alert_notify executes a Python callback directly from
        # libtorrent's internal thread, requiring PyGILState_Ensure. When Python
        # calls any synchronous libtorrent method (e.g. handle.trackers(), status()),
        # Python holds the GIL, causing a circular deadlock if an alert fires.
        # set_alert_fd writes a byte to a non-blocking socket from C++ without
        # touching Python or acquiring the GIL.
        use_alert_fd = False
        set_alert_fd_fn = getattr(self.session, "set_alert_fd", None) if self.session is not None else None
        if callable(set_alert_fd_fn):
            try:
                self._notify_r, self._notify_w = socket.socketpair()
                self._notify_r.setblocking(False)
                self._notify_w.setblocking(False)
                set_alert_fd_fn(self._notify_w.fileno())
                self.loop.add_reader(self._notify_r.fileno(), self._on_alert_fd_readable)
                use_alert_fd = True
            except (NotImplementedError, AttributeError, OSError) as e:
                log.warning(f"Failed to configure set_alert_fd: {e}; falling back to set_alert_notify")
                if self._notify_r is not None:
                    try:
                        self._notify_r.close()
                    except Exception:
                        pass
                    self._notify_r = None
                if self._notify_w is not None:
                    try:
                        self._notify_w.close()
                    except Exception:
                        pass
                    self._notify_w = None

        if not use_alert_fd and self.session is not None:
            self.session.set_alert_notify(self.alert_notify)

        self.event.set()

    async def stop(self):
        log.debug("Alert stopping..")
        self.run = False
        self.event.set()

        set_alert_fd_fn = getattr(self.session, "set_alert_fd", None) if self.session is not None else None
        if callable(set_alert_fd_fn):
            try:
                set_alert_fd_fn(-1)
            except Exception:
                pass

        if self.loop is not None and self._notify_r is not None:
            try:
                self.loop.remove_reader(self._notify_r.fileno())
            except Exception:
                pass

        if self._notify_r is not None:
            try:
                self._notify_r.close()
            except Exception:
                pass
            self._notify_r = None

        if self._notify_w is not None:
            try:
                self._notify_w.close()
            except Exception:
                pass
            self._notify_w = None

        await asyncio.sleep(0)
        if self.pop_alerts_task:
            try:
                await self.pop_alerts_task
            except asyncio.CancelledError:
                pass
            self.pop_alerts_task = None
        log.debug("Alert stopped.")

    def register_handler(self, alert_type, handler):
        if alert_type not in self.alert_types and alert_type not in self.categories:
            raise ValueError("Not a valid alert type or category.")
        if not inspect.iscoroutinefunction(handler):
            raise ValueError("Alert handlers must be coroutine functions.")
        self.handlers.setdefault(alert_type, []).append(handler)

    def _on_alert_fd_readable(self):
        if self._notify_r is not None:
            try:
                while True:
                    data = self._notify_r.recv(4096)
                    if not data:
                        break
            except (BlockingIOError, InterruptedError):
                pass
            except Exception:
                pass
        self.event.set()

    def alert_notify(self):
        # Fallback if set_alert_fd is unavailable
        if self.loop is None:
            return
        self.loop.call_soon_threadsafe(self.event.set)

    async def pop_alerts(self):
        while self.run:
            await self.event.wait()
            self.event.clear()

            tasks = []
            if self.session is None or self.loop is None:
                continue
            for alert in self.session.pop_alerts():
                handlers = set()
                handlers.update(self.handlers.get(type(alert).__name__, []))

                for k, v in self.categories.items():
                    if alert.category() & v:
                        handlers.update(self.handlers.get(k, []))
                for handler in handlers:
                    tasks.append(self.loop.create_task(handler(alert)))

            # We have to make sure all alert handlers have completed before
            # calling pop_alerts() again as it will invalidate all previous
            # libtorrent alert objects.
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    log.error(f"Error in alert handler: {res}")
