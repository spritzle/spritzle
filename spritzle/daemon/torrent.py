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
        self.core.alert.register_handler(
            "torrent_removed_alert", self._on_torrent_removed_alert
        )
        self.core.alert.register_handler(
            "torrent_deleted_alert", self._on_torrent_deleted_alert
        )
        self.core.alert.register_handler(
            "torrent_delete_failed_alert", self._on_torrent_delete_failed_alert
        )

    async def remove(self, torrent_handle, options=0):
        info_hash = str(torrent_handle.info_hash())

        if (
            info_hash not in self.remove_torrent_futures
            and info_hash not in self.delete_torrent_futures
        ):
            self.remove_torrent_futures[info_hash] = asyncio.Future()
            if options & lt.options_t.delete_files:
                self.delete_torrent_futures[info_hash] = asyncio.Future()
            self.core.session.remove_torrent(torrent_handle, options)

        futures = []
        if info_hash in self.remove_torrent_futures:
            futures.append(self.remove_torrent_futures[info_hash])
        if info_hash in self.delete_torrent_futures:
            futures.append(self.delete_torrent_futures[info_hash])
        await asyncio.gather(*futures)

    async def _on_torrent_removed_alert(self, alert):
        future = self.remove_torrent_futures.pop(str(alert.info_hash))
        future.set_result(alert)

    async def _on_torrent_deleted_alert(self, alert):
        future = self.delete_torrent_futures.pop(str(alert.info_hash))
        future.set_result(alert)

    async def _on_torrent_delete_failed_alert(self, alert):
        future = self.delete_torrent_futures.pop(str(alert.info_hash))
        future.set_exception(AlertException(alert))
