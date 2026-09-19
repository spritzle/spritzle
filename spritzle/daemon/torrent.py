#
# spritzle/torrent.py
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
import logging
from typing import Optional

import libtorrent as lt

log = logging.getLogger("spritzle")


class AlertException(Exception):
    def __init__(self, alert):
        self.alert = alert


class Torrent(object):
    def __init__(self, core):
        self.core = core
        self.remove_torrent_futures = {}
        self.delete_torrent_futures = {}
        self.in_flight_options = {}
        self.core.alert.register_handler(
            "torrent_removed_alert", self._on_torrent_removed_alert
        )
        self.core.alert.register_handler(
            "torrent_deleted_alert", self._on_torrent_deleted_alert
        )
        self.core.alert.register_handler(
            "torrent_delete_failed_alert", self._on_torrent_delete_failed_alert
        )

    async def remove(self, torrent_handle, options=0, timeout: Optional[float] = 30.0):
        info_hash = str(torrent_handle.info_hash())
        loop = asyncio.get_running_loop()

        remove_fut = loop.create_future()
        self.remove_torrent_futures.setdefault(info_hash, set()).add(remove_fut)

        needs_delete = bool(options & lt.options_t.delete_files)
        delete_fut = None
        if needs_delete:
            delete_fut = loop.create_future()
            self.delete_torrent_futures.setdefault(info_hash, set()).add(delete_fut)

        active_options = self.in_flight_options.get(info_hash)
        if active_options is None:
            self.in_flight_options[info_hash] = int(options)
            self.core.session.remove_torrent(torrent_handle, options)
        elif needs_delete and not (active_options & lt.options_t.delete_files):
            escalated = active_options | int(lt.options_t.delete_files)
            self.in_flight_options[info_hash] = escalated
            self.core.session.remove_torrent(torrent_handle, escalated)

        wait_futs = [remove_fut]
        if delete_fut is not None:
            wait_futs.append(delete_fut)

        try:
            if timeout is not None:
                await asyncio.wait_for(asyncio.gather(*wait_futs), timeout=timeout)
            else:
                await asyncio.gather(*wait_futs)
        finally:
            if info_hash in self.remove_torrent_futures:
                self.remove_torrent_futures[info_hash].discard(remove_fut)
                if not self.remove_torrent_futures[info_hash]:
                    self.remove_torrent_futures.pop(info_hash, None)
            if delete_fut is not None and info_hash in self.delete_torrent_futures:
                self.delete_torrent_futures[info_hash].discard(delete_fut)
                if not self.delete_torrent_futures[info_hash]:
                    self.delete_torrent_futures.pop(info_hash, None)
            if (
                info_hash not in self.remove_torrent_futures
                and info_hash not in self.delete_torrent_futures
            ):
                self.in_flight_options.pop(info_hash, None)

    async def _on_torrent_removed_alert(self, alert):
        ih = str(alert.info_hash)
        waiters = self.remove_torrent_futures.pop(ih, set())
        for future in list(waiters):
            if not future.done():
                future.set_result(alert)
        if ih not in self.remove_torrent_futures and ih not in self.delete_torrent_futures:
            self.in_flight_options.pop(ih, None)

    async def _on_torrent_deleted_alert(self, alert):
        ih = str(alert.info_hash)
        waiters = self.delete_torrent_futures.pop(ih, set())
        for future in list(waiters):
            if not future.done():
                future.set_result(alert)
        if ih not in self.remove_torrent_futures and ih not in self.delete_torrent_futures:
            self.in_flight_options.pop(ih, None)

    async def _on_torrent_delete_failed_alert(self, alert):
        ih = str(alert.info_hash)
        waiters = self.delete_torrent_futures.pop(ih, set())
        for future in list(waiters):
            if not future.done():
                future.set_exception(AlertException(alert))
        if ih not in self.remove_torrent_futures and ih not in self.delete_torrent_futures:
            self.in_flight_options.pop(ih, None)

