#
# spritzle/resume_data.py
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
import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, Optional, Set


import libtorrent as lt

log = logging.getLogger("spritzle")


def decode_bencoded_value(val: Any) -> Any:
    """Recursively decode bencoded byte strings into python strings."""
    if isinstance(val, bytes):
        try:
            return val.decode("utf-8")
        except UnicodeDecodeError:
            return val.decode("latin1")
    elif isinstance(val, list):
        return [decode_bencoded_value(item) for item in val]
    elif isinstance(val, dict):
        return {
            (k.decode("utf-8") if isinstance(k, bytes) else k): decode_bencoded_value(v)
            for k, v in val.items()
        }
    return val


def _atomic_write_file(path: Path, data: bytes, is_deleted: Callable[[], bool]) -> None:
    """Atomically write data to path, checking if the file was marked deleted."""
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}_{time.monotonic_ns()}.tmp")
    try:
        tmp_path.write_bytes(data)
        if is_deleted():
            tmp_path.unlink(missing_ok=True)
            return
        tmp_path.replace(path)
        if is_deleted():
            path.unlink(missing_ok=True)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


class ResumeData(object):
    def __init__(self, core):
        self.core = core
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.save_loop_task = None

        # Store state of outstanding save resume data alerts
        self.resume_data_futures: Dict[str, asyncio.Future] = {}
        self.pending_writes: Set[asyncio.Task] = set()
        self.deleted_hashes: Set[str] = set()
        self.save_interval = 60 * 30

    async def start(self):
        self.loop = asyncio.get_running_loop()
        log.debug("Resume data manager starting...")
        await self.load()
        self.core.alert.register_handler(
            "save_resume_data_alert", self.on_save_resume_data_alert
        )
        self.core.alert.register_handler(
            "save_resume_data_failed_alert", self.on_save_resume_data_failed_alert
        )
        self.save_loop_task = self.loop.create_task(self.save_loop())

    async def stop(self):
        log.debug("Resume data manager stopping...")
        if self.save_loop_task:
            self.save_loop_task.cancel()
            try:
                await self.save_loop_task
            except asyncio.CancelledError:
                pass
        await self.save_all()
        
        if self.pending_writes:
            log.debug(f"Waiting for {len(self.pending_writes)} pending resume data writes...")
            await asyncio.gather(*self.pending_writes, return_exceptions=True)
            
        log.debug("ResumeData stopped.")

    async def save_loop(self):
        save_all_task = None
        try:
            while True:
                freq_val = self.core.config.get("resume_data_save_frequency", 60)
                try:
                    freq = float(freq_val)
                    if freq <= 0:
                        freq = 60.0
                except (TypeError, ValueError):
                    freq = 60.0
                await asyncio.sleep(freq)
                # Don't interrupt save process when loop is cancelled
                if self.loop is not None:
                    save_all_task = self.loop.create_task(self.save_all())
                    await asyncio.shield(save_all_task)
        except asyncio.CancelledError:
            if save_all_task and not save_all_task.done():
                await save_all_task


    async def on_save_resume_data_alert(self, alert):
        info_hash = str(alert.handle.info_hash())
        if info_hash in self.deleted_hashes:
            log.debug(f"Ignoring save resume data alert for deleted torrent {info_hash}")
            return

        p = Path(self.core.state_dir, info_hash + ".resume")
        r = lt.write_resume_data(alert.params)
        if info_hash in self.core.torrent_data:
            r.update(self.core.torrent_data[info_hash])
        
        data = lt.bencode(r)
        
        fut = self.resume_data_futures.get(info_hash)
        # Fire-and-forget write task to avoid blocking the alert loop
        loop = self.loop or asyncio.get_running_loop()
        task = loop.create_task(self._write_data(p, data, info_hash, fut))
        self.pending_writes.add(task)
        task.add_done_callback(self.pending_writes.discard)

    async def _write_data(
        self, path: Path, data: bytes, info_hash: str, fut: Optional[asyncio.Future] = None
    ):
        try:
            if info_hash in self.deleted_hashes:
                return
            loop = self.loop or asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                _atomic_write_file,
                path,
                data,
                lambda: info_hash in self.deleted_hashes,
            )
            if info_hash in self.deleted_hashes:
                path.unlink(missing_ok=True)
        except Exception as e:
            log.error(f"Failed to write resume data for {info_hash}: {e}")
        finally:
            if fut is not None and not fut.done():
                fut.set_result(True)
            if self.resume_data_futures.get(info_hash) is fut:
                self.resume_data_futures.pop(info_hash, None)

    async def on_save_resume_data_failed_alert(self, alert):
        log.error(
            f"Error saving resume_data for torrent {alert.torrent_name} "
            f"error: {alert.error.message()}"
        )
        info_hash = str(alert.handle.info_hash())
        if info_hash in self.resume_data_futures:
            # We don't really care if this fails right now, maybe in the future
            # we should raise an exception.
            fut = self.resume_data_futures.pop(info_hash)
            if not fut.done():
                fut.set_result(True)

    def save_torrent(self, torrent_handle):
        info_hash = str(torrent_handle.info_hash())
        self.deleted_hashes.discard(info_hash)
        if info_hash not in self.resume_data_futures:
            self.resume_data_futures[info_hash] = asyncio.Future()
            torrent_handle.save_resume_data(
                flags=(
                    int(lt.save_resume_flags_t.flush_disk_cache)
                    | int(lt.save_resume_flags_t.save_info_dict)
                )
            )
        return self.resume_data_futures[info_hash]

    async def save_all(self):
        log.debug("Saving resume data for all torrents")
        if self.core.session is None:
            return
        for torrent in self.core.session.get_torrents():
            if torrent.need_save_resume_data():
                self.save_torrent(torrent)
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *list(self.resume_data_futures.values()), return_exceptions=True
                ),
                timeout=30.0,
            )

        except asyncio.TimeoutError:
            log.warning("Timed out waiting for resume data to save")
            for h, fut in list(self.resume_data_futures.items()):
                if not fut.done():
                    fut.cancel()
                    self.resume_data_futures.pop(h, None)
                elif fut.cancelled():
                    self.resume_data_futures.pop(h, None)
        except Exception as e:
            log.error(f"Error saving resume data: {e}")

    def delete(self, info_hash):
        self.deleted_hashes.add(info_hash)
        if info_hash in self.resume_data_futures:
            fut = self.resume_data_futures.pop(info_hash)
            if not fut.done():
                fut.cancel()

        p = Path(self.core.state_dir, info_hash + ".resume")
        p.unlink(missing_ok=True)

        if self.core.state_dir.is_dir():
            for tmp in self.core.state_dir.glob(f"*.{info_hash}.*.tmp"):
                tmp.unlink(missing_ok=True)

    async def load(self):
        log.info(f"Loading resume data from {self.core.state_dir}")
        for f in self.core.state_dir.iterdir():
            if f.suffix == ".resume" and not f.name.startswith("."):
                log.info(f"Found {f.name}, attempting add..")
                try:
                    b = f.read_bytes()
                    atp = lt.read_resume_data(b)
                    handle = await asyncio.get_running_loop().run_in_executor(
                        None, functools.partial(self.core.session.add_torrent), atp
                    )
                    d = lt.bdecode(b)
                    if isinstance(d, dict):
                        info_hash = str(handle.info_hash())
                        self.core.torrent_data[info_hash] = {}
                        for key, value in d.items():
                            if key.startswith(b"spritzle."):
                                self.core.torrent_data[info_hash][key.decode()] = (
                                    decode_bencoded_value(value)
                                )
                except Exception as e:
                    log.error(f"Error loading resume data {f}: {e}")
                    continue


