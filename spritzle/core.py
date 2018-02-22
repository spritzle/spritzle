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
from pathlib import Path
import logging
import functools
import binascii

import libtorrent as lt

from spritzle.alert import Alert
from spritzle.hooks import Hooks

log = logging.getLogger('spritzle')


class Core(object):

    def __init__(self, config, state_dir=None):
        self.config = config
        self.session = None
        self.hooks = Hooks(Path(self.config.dir, 'hooks'))
        if state_dir is None:
            self.state_dir = Path(
                Path.home(), '.local', 'share', 'spritzle', 'state')
        else:
            self.state_dir = state_dir
        # TODO check dir for rw, etc
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.session_stats_future = None
        # A place to keep additional data on torrents, that isn't stored in
        # libtorrent.  This is key'd on info_hash.
        self.torrent_data = {}

        self.alert = Alert()
        self.alert.register_handler(
            'session_stats_alert',
            self.on_session_stats_alert
        )
        self.alert.register_handler(
            'status_notification',
            self.on_status_notification_alert
        )
        self.alert.register_handler(
            'save_resume_data_alert',
            self.on_save_resume_data_alert
        )
        self.alert.register_handler(
            'save_resume_data_failed_alert',
            self.on_save_resume_data_failed_alert
        )
        self.alert.register_handler(
            'add_torrent_alert',
            self.on_add_torrent_alert
        )

    async def start(self, settings=None):
        log.debug('Core starting..')
        if settings is None:
            settings = {
                'alert_mask':
                    (
                        int(lt.alert.category_t.error_notification) |
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
                        int(lt.alert.category_t.peer_log_notification)
                    ),
                'user_agent': 'Spritzle/%s libtorrent/%s' % (
                    pkg_resources.require("spritzle")[0].version,
                    lt.__version__),
            }
        self.session = lt.session(settings)

        await self.alert.start(self.session)
        await self.load_resume_data()
        log.debug('Core started.')

    async def stop(self):
        log.debug('Core stopping..')
        await self.alert.stop()
        del self.session
        self.session = None
        log.debug('Core stopped..')

    async def load_resume_data(self):
        log.info(f'Loading resume data from {self.state_dir}')
        for f in self.state_dir.iterdir():
            if f.suffix == '.resume':
                log.info(f'Found {f.name}, attempting add..')
                b = f.read_bytes()
                atp = lt.read_resume_data(b)
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, functools.partial(self.session.add_torrent), atp)
                except RuntimeError as e:
                    log.error(f'Error loading resume data {f}: {e}')

                d = lt.bdecode(b)

                info_hash = binascii.hexlify(d[b'info-hash']).decode()
                self.torrent_data[info_hash] = {}
                for key, value in d.items():
                    if key.startswith(b'spritzle.'):
                        self.torrent_data[info_hash][key.decode()] = value

    async def on_session_stats_alert(self, alert):
        self.session_stats_future.set_result(alert.values)

    async def get_session_status(self):
        if self.session_stats_future is None or \
                self.session_stats_future.done():
            self.session_stats_future = asyncio.Future()
            self.session.post_session_stats()

        await self.session_stats_future
        return self.session_stats_future.result()

    def get_torrent_tags(self, info_hash):
        return self.torrent_data.get(info_hash, {}).get('spritzle.tags', [])

    async def on_status_notification_alert(self, alert):
        if hasattr(alert, 'handle'):
            if alert.what() == 'torrent_removed_alert':
                info_hash = str(alert.info_hash)
            info_hash = str(alert.handle.info_hash())
            self.hooks.run_hooks(
                alert.what(),
                info_hash,
                ','.join(self.get_torrent_tags(info_hash)))

    def save_resume_data(self):
        for torrent in self.core.get_torrents():
            if torrent.need_save_resume_data():
                torrent.save_resume_data(
                    flags=(
                        int(lt.save_resume_flags_t.flush_disk_cache) |
                        int(lt.save_resume_flags_t.save_info_dict)
                    ),
                )

    async def on_save_resume_data_alert(self, alert):
        p = Path(self.state_dir, alert.torrent_name + '.resume')
        r = lt.write_resume_data(alert.params)
        print(self.torrent_data)
        r.update(self.torrent_data[str(alert.handle.info_hash())])
        p.write_bytes(lt.bencode(r))

    async def on_save_resume_data_failed_alert(self, alert):
        log.error(
            f'Error saving resume_data for torrent {alert.torrent_name} '
            f'error: {alert.error.message()}')

    async def on_add_torrent_alert(self, alert):
        log.info('add_torrent_alert saving resume data')
        try:
            alert.handle.save_resume_data()
        except RuntimeError as e:
            # An invalid handle can occur here if a torrent is added and
            # removed is quick succession.
            log.error(e)
