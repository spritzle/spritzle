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
import importlib.metadata
from pathlib import Path
import logging
import functools
from typing import Any, Dict, List, Optional, Sequence, Set, cast

import libtorrent as lt

from .alert import Alert
from .config import Config
from .hooks import Hooks
from .resume_data import ResumeData
from .torrent import Torrent

log = logging.getLogger("spritzle")


class Core(object):
    def __init__(self, config: Config, state_dir: Optional[Path] = None):
        self.config = config
        self.session: Optional[lt.session] = None
        self.hooks = Hooks(Path(self.config.path, "hooks"))
        if state_dir is None:
            self.state_dir = Path(Path.home(), ".local", "share", "spritzle", "state")
        else:
            self.state_dir = state_dir
        # TODO check dir for rw, etc
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.session_stats_waiters: Set[asyncio.Future] = set()
        # A place to keep additional data on torrents, that isn't stored in
        # libtorrent.  This is key'd on info_hash.
        self.torrent_data: Dict[str, Any] = {}
        self._baseline_settings: Optional[Dict[str, Any]] = None

        self.alert = Alert()
        self.resume_data = ResumeData(self)
        self.torrent = Torrent(self)
        self.alert.register_handler("session_stats_alert", self.on_session_stats_alert)
        self.alert.register_handler(
            "status_notification", self.on_status_notification_alert
        )
        self.alert.register_handler("state_changed_alert", self.on_state_changed_alert)

    def get_default_settings(self) -> Dict[str, Any]:
        return {
            "alert_mask": (
                int(lt.alert.category_t.error_notification)
                | int(lt.alert.category_t.peer_notification)
                | int(lt.alert.category_t.port_mapping_notification)
                | int(lt.alert.category_t.storage_notification)
                | int(lt.alert.category_t.tracker_notification)
                | int(lt.alert.category_t.status_notification)
                | int(lt.alert.category_t.ip_block_notification)
                | int(lt.alert.category_t.performance_warning)
                | int(lt.alert.category_t.stats_notification)
                | int(lt.alert.category_t.session_log_notification)
                | int(lt.alert.category_t.torrent_log_notification)
                | int(lt.alert.category_t.peer_log_notification)
            ),
            "user_agent": "Spritzle/%s libtorrent/%s"
            % (importlib.metadata.version("spritzle"), lt.__version__),
            "alert_queue_size": 20000,
        }

    def get_baseline_settings(self) -> Dict[str, Any]:
        if self._baseline_settings is None:
            temp_session = cast(Any, lt.session(self.get_default_settings()))
            self._baseline_settings = temp_session.get_settings()
        return dict(self._baseline_settings)

    def reset_settings(
        self, keys: Optional[Sequence[str]] = None, reset_all: bool = False
    ) -> List[str]:
        if self.session is None:
            raise RuntimeError("Session not started")
        baseline = self.get_baseline_settings()
        if reset_all:
            target_keys = list(baseline.keys())
        elif keys:
            target_keys = list(keys)
        else:
            raise ValueError("Either keys or reset_all must be specified.")

        for k in target_keys:
            if k not in baseline:
                raise KeyError(f"Unknown setting '{k}'")

        reset_dict = {k: baseline[k] for k in target_keys}
        cast(Any, self.session).apply_settings(reset_dict)
        return target_keys

    async def start(self, settings: Optional[Dict[str, Any]] = None) -> None:
        log.debug("Core starting..")
        if settings is None:
            settings = self.get_default_settings()
        self.session = lt.session(settings)
        await self.load_session_state()
        await self.alert.start(self.session)
        await self.resume_data.start()

        # Consistency check: Ensure all torrents have metadata entries
        # This handles cases where session.state restores a torrent but resume data (metadata) is missing.
        for handle in self.session.get_torrents():
            info_hash = str(handle.info_hash())
            if info_hash not in self.torrent_data:
                log.warning(f"Restoring missing metadata for ghost torrent {info_hash}")
                self.torrent_data[info_hash] = {}
                
        log.debug("Core started.")

    async def stop(self):
        log.debug("Core stopping..")
        if self.session is None:
            return
        await self.resume_data.stop()
        await self.save_session_state()
        self.session.pause()
        await self.alert.stop()
        del self.session
        self.session = None
        log.debug("Core stopped..")

    async def save_session_state(self):
        if self.session is None:
            return
        state = await asyncio.get_running_loop().run_in_executor(
            None, functools.partial(self.session.save_state)
        )
        f = Path(self.state_dir, "session.state")
        f.write_bytes(lt.bencode(state))

    async def load_session_state(self):
        f = Path(self.state_dir, "session.state")
        log.info(f"Loading session state from: {f}")
        if f.exists():
            if self.session is None:
                raise RuntimeError("Session not started")
            await asyncio.get_running_loop().run_in_executor(
                None, functools.partial(self.session.load_state), f.read_bytes()
            )

    async def on_session_stats_alert(self, alert):
        waiters = list(self.session_stats_waiters)
        self.session_stats_waiters.clear()
        for fut in waiters:
            if not fut.done():
                fut.set_result(alert.values)

    async def get_session_stats(self):
        if self.session is None:
            raise RuntimeError("Session not started")
        loop = asyncio.get_running_loop()
        first_caller = len(self.session_stats_waiters) == 0
        fut = loop.create_future()
        self.session_stats_waiters.add(fut)
        if first_caller:
            self.session.post_session_stats()

        try:
            return await asyncio.wait_for(fut, timeout=5.0)
        finally:
            self.session_stats_waiters.discard(fut)


    def get_torrent_tags(self, info_hash):
        tags = self.torrent_data.get(info_hash, {}).get("spritzle.tags")
        if not tags:
            return []
        return [str(t) for t in tags]


    async def on_status_notification_alert(self, alert):
        try:
            if hasattr(alert, "info_hash"):
                info_hash = str(alert.info_hash)
            elif hasattr(alert, "handle"):
                info_hash = str(alert.handle.info_hash())
            else:
                return

            self.hooks.run_hooks(
                alert.what(), info_hash, ",".join(self.get_torrent_tags(info_hash))
            )
        except Exception:
            import traceback

            log.error(
                f"Error in on_status_notification_alert: {traceback.format_exc()}"
            )

    async def on_state_changed_alert(self, alert):
        if alert.handle.need_save_resume_data():
            self.resume_data.save_torrent(alert.handle)
