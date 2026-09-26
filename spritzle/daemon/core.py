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
import functools
import logging
import os
from pathlib import Path
import signal
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Union, cast

import libtorrent as lt

from .alert import Alert
from .api_keys import KeyManager
from .config import Config
from .hooks import Hooks
from .identity import Identity
from .resume_data import ResumeData
from .torrent import Torrent

log = logging.getLogger("spritzle")


class Core(object):
    def __init__(
        self,
        config: Config,
        state_dir: Optional[Union[Path, str]] = None,
        startup_listen_interfaces: Optional[str] = None,
    ):
        self.config = config
        self.start_time = time.time()
        self.session: Optional[lt.session] = None
        self.startup_listen_interfaces = startup_listen_interfaces

        self.hooks = Hooks(Path(self.config.path, "hooks"))
        if state_dir is not None:
            self.state_dir = Path(state_dir).expanduser()
        else:
            env_state_dir = os.environ.get("SPRITZLE_STATE_DIR")
            if env_state_dir:
                self.state_dir = Path(env_state_dir).expanduser()
            elif config and config.get("state_dir"):
                self.state_dir = Path(str(config.get("state_dir"))).expanduser()
            else:
                self.state_dir = Path(Path.home(), ".local", "share", "spritzle", "state")
        # TODO check dir for rw, etc
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.identity = Identity(self.state_dir)
        self.key_manager = KeyManager(self.state_dir)
        self.session_stats_waiters: Set[asyncio.Future] = set()
        # A place to keep additional data on torrents, that isn't stored in
        # libtorrent.  This is key'd on info_hash.
        self.torrent_data: Dict[str, Any] = {}
        self._baseline_settings: Optional[Dict[str, Any]] = None

        self.alert = Alert()
        self.resume_data = ResumeData(self)
        self.torrent = Torrent(self)

        self._tasks: Set[asyncio.Task] = set()
        self._config_watch_task: Optional[asyncio.Task] = None
        self._sighup_installed = False
        self.config.add_change_callback(self._on_config_changed)

        self.alert.register_handler("session_stats_alert", self.on_session_stats_alert)
        self.alert.register_handler(
            "status_notification", self.on_status_notification_alert
        )
        self.alert.register_handler("state_changed_alert", self.on_state_changed_alert)
        self.alert.register_handler("file_error_alert", self.on_file_error_alert)
        self.alert.register_handler("torrent_error_alert", self.on_torrent_error_alert)
        self.alert.register_handler("storage_moved_alert", self.on_storage_moved_alert)
        self.alert.register_handler(
            "storage_moved_failed_alert", self.on_storage_moved_failed_alert
        )

    def get_default_settings(self) -> Dict[str, Any]:
        try:
            version_str = importlib.metadata.version("spritzle")
        except Exception:
            version_str = "1.0.0"

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
            "user_agent": f"Spritzle/{version_str} libtorrent/{lt.__version__}",
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

        explicit_interfaces = (
            getattr(self, "startup_listen_interfaces", None)
            or settings.get("listen_interfaces")
            or self.config.get("listen_interfaces")
            or os.environ.get("SPRITZLE_LISTEN_INTERFACES")
        )
        if explicit_interfaces:
            settings["listen_interfaces"] = str(explicit_interfaces).strip()

        self.session = lt.session(settings)
        await self.load_session_state()
        if explicit_interfaces and self.session is not None:
            cast(Any, self.session).apply_settings({"listen_interfaces": str(explicit_interfaces).strip()})
        await self.alert.start(self.session)
        await self.resume_data.start()

        # Consistency check: Ensure all torrents have metadata entries
        # This handles cases where session.state restores a torrent but resume data (metadata) is missing.
        for handle in self.session.get_torrents():
            info_hash = str(handle.info_hash())
            if info_hash not in self.torrent_data:
                log.warning(f"Restoring missing metadata for ghost torrent {info_hash}")
                self.torrent_data[info_hash] = {}
        self._validate_default_save_path()
        self._setup_signals()
        self._start_config_watcher()

        log.debug("Core started.")

    async def stop(self, save: bool = True):
        log.debug("Core stopping..")
        self._cleanup_signals()
        await self._stop_config_watcher()
        self.config.remove_change_callback(self._on_config_changed)
        if self._tasks:
            for t in list(self._tasks):
                t.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()
        await self.hooks.stop()
        await self.resume_data.stop(save=save)
        if self.session is not None:
            if save:
                await self.save_session_state()
            self.session.pause()
        await self.alert.stop()
        if self.session is not None:
            del self.session
            self.session = None
        log.debug("Core stopped..")

    def _on_config_changed(self, cfg: Config) -> None:
        self._validate_default_save_path()
        self.resume_data.notify_interval_changed()

    def _validate_default_save_path(self) -> None:
        default_save_path = self.config.get("default_save_path")
        if default_save_path:
            p = Path(os.path.expanduser(str(default_save_path)))
            if not p.exists():
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    log.info(f"Created default download directory: {p}")
                except Exception as e:
                    log.warning(f"Default download directory '{p}' could not be created: {e}")
            elif not os.access(p, os.W_OK | os.X_OK):
                log.warning(f"Default download directory '{p}' is not writable!")

    def _setup_signals(self) -> None:
        if hasattr(signal, "SIGHUP"):
            try:
                loop = asyncio.get_running_loop()
                loop.add_signal_handler(signal.SIGHUP, self._on_sighup)
                self._sighup_installed = True
            except (ValueError, RuntimeError, NotImplementedError):
                self._sighup_installed = False

    def _cleanup_signals(self) -> None:
        if self._sighup_installed and hasattr(signal, "SIGHUP"):
            try:
                loop = asyncio.get_running_loop()
                loop.remove_signal_handler(signal.SIGHUP)
            except (ValueError, RuntimeError, NotImplementedError):
                pass
            self._sighup_installed = False

    def _on_sighup(self) -> None:
        log.info("Received SIGHUP, reloading configuration...")
        t = asyncio.create_task(self.reload_config(force=True))
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    def _start_config_watcher(self) -> None:
        if self._config_watch_task is None and not self.config.in_memory and self.config.config_file is not None:
            loop = asyncio.get_running_loop()
            self._config_watch_task = loop.create_task(self._config_watch_loop())

    async def _stop_config_watcher(self) -> None:
        if self._config_watch_task is not None:
            self._config_watch_task.cancel()
            try:
                await self._config_watch_task
            except asyncio.CancelledError:
                pass
            self._config_watch_task = None

    async def _config_watch_loop(self) -> None:
        try:
            while True:
                interval_val = self.config.get("config_watch_interval", 2.0)
                try:
                    interval = float(interval_val)
                    if interval <= 0:
                        interval = 2.0
                except (TypeError, ValueError):
                    interval = 2.0
                await asyncio.sleep(interval)
                await self.reload_config()
        except asyncio.CancelledError:
            pass

    async def reload_config(self, force: bool = False) -> bool:
        """Reload configuration from disk and apply dynamic updates.

        Returns True if configuration changed and was reloaded, False otherwise.
        """
        reloaded = self.config.reload(force=force)
        if reloaded:
            if self.session is not None:
                configured_interfaces = self.config.get("listen_interfaces")
                if configured_interfaces:
                    try:
                        cast(Any, self.session).apply_settings({"listen_interfaces": str(configured_interfaces).strip()})
                    except Exception as e:
                        log.error(f"Failed to apply reloaded listen_interfaces: {e}")
            log.info("Configuration reload successfully applied to daemon runtime.")
        return reloaded

    async def save_session_state(self):
        if self.session is None:
            return
        state = await asyncio.get_running_loop().run_in_executor(
            None, functools.partial(self.session.save_state)
        )
        f = Path(self.state_dir, "session.state")
        data = lt.bencode(state)
        tmp = f.with_name(f".{f.name}.tmp")
        def _write_atomic():
            tmp.write_bytes(data)
            tmp.replace(f)
        await asyncio.get_running_loop().run_in_executor(None, _write_atomic)

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
        if alert.handle.is_valid() and alert.handle.need_save_resume_data():
            self.resume_data.save_torrent(alert.handle)

    async def on_file_error_alert(self, alert):
        info_hash = str(alert.handle.info_hash()) if alert.handle.is_valid() else ""
        msg = f"File error in torrent {info_hash}: {alert.message()}"
        log.error(msg)
        if info_hash:
            self.torrent_data.setdefault(info_hash, {})["last_error"] = alert.message()
            self.hooks.run_hooks(
                "file_error_alert", info_hash, ",".join(self.get_torrent_tags(info_hash))
            )

    async def on_torrent_error_alert(self, alert):
        info_hash = str(alert.handle.info_hash()) if alert.handle.is_valid() else ""
        msg = f"Torrent error in {info_hash}: {alert.message()}"
        log.error(msg)
        if info_hash:
            self.torrent_data.setdefault(info_hash, {})["last_error"] = alert.message()
            self.hooks.run_hooks(
                "torrent_error_alert", info_hash, ",".join(self.get_torrent_tags(info_hash))
            )

    async def on_storage_moved_alert(self, alert):
        info_hash = str(alert.handle.info_hash()) if alert.handle.is_valid() else ""
        if info_hash:
            if alert.handle.is_valid():
                self.resume_data.save_torrent(alert.handle)
            self.hooks.run_hooks(
                "storage_moved_alert", info_hash, ",".join(self.get_torrent_tags(info_hash))
            )

    async def on_storage_moved_failed_alert(self, alert):
        info_hash = str(alert.handle.info_hash()) if alert.handle.is_valid() else ""
        msg = f"Storage move failed for torrent {info_hash}: {alert.message()}"
        log.error(msg)
        if info_hash:
            self.torrent_data.setdefault(info_hash, {})["last_error"] = alert.message()
            self.hooks.run_hooks(
                "storage_moved_failed_alert", info_hash, ",".join(self.get_torrent_tags(info_hash))
            )
