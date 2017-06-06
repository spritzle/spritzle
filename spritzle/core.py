#
# spritzle/core.py
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
import pkg_resources

import libtorrent as lt

from spritzle.alert import Alert


class Core(object):
    def __init__(self):
        self.session = None

        self.alert = Alert()
        self.alert.register_handler(
            'session_stats_alert',
            self.on_session_stats_alert
        )

        self.session_stats_future = None

        # A place to keep additional data on torrents, that isn't stored in
        # libtorrent.  This is key'd on info_hash.
        self.torrent_data = {}

    def start(self):
        self.session = lt.session({
            'alert_mask': (int(lt.alert.category_t.error_notification) |
                           int(lt.alert.category_t.peer_notification) |
                           int(lt.alert.category_t.port_mapping_notification) |
                           int(lt.alert.category_t.storage_notification) |
                           int(lt.alert.category_t.tracker_notification) |
                           int(lt.alert.category_t.status_notification) |
                           int(lt.alert.category_t.ip_block_notification) |
                           int(lt.alert.category_t.performance_warning) |
                           int(lt.alert.category_t.stats_notification) |
                           int(lt.alert.category_t.session_log_notification) |
                           int(lt.alert.category_t.torrent_log_notification) |
                           int(lt.alert.category_t.peer_log_notification)),
            'user_agent': 'Spritzle/%s libtorrent/%s' % (
                pkg_resources.require("spritzle")[0].version,
                lt.__version__),
            })

        self.alert.start(self.session)

    def stop(self):
        self.alert.stop()

    def on_session_stats_alert(self, alert):
        self.session_stats_future.set_result(alert.values)

    async def get_session_status(self):
        if self.session_stats_future is None or \
                self.session_stats_future.done():
            self.session_stats_future = asyncio.Future()
            self.session.post_session_stats()

        await self.session_stats_future
        return self.session_stats_future.result()
