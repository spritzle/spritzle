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
from pathlib import Path
from typing import Dict, Optional, Set


import libtorrent as lt

log = logging.getLogger("spritzle")


class ResumeData(object):
    def __init__(self, core):
        self.core = core
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.save_loop_task = None

        # Store state of outstanding save resume data alerts
        self.resume_data_futures: Dict[str, asyncio.Future] = {}
        self.pending_writes: Set[asyncio.Task] = set()
        self.save_interval = 60 * 30

    async def start(self):
        self.loop = asyncio.get_event_loop()
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
                await asyncio.sleep(self.core.config["resume_data_save_frequency"])
                # Don't interrupt save process when loop is cancelled
                if self.loop is not None:
                    save_all_task = self.loop.create_task(self.save_all())
                    await asyncio.shield(save_all_task)
        except asyncio.CancelledError:
            if save_all_task and not save_all_task.done():
                await save_all_task

    async def on_save_resume_data_alert(self, alert):
        info_hash = str(alert.handle.info_hash())
        p = Path(self.core.state_dir, info_hash + ".resume")
        r = lt.write_resume_data(alert.params)
        if info_hash in self.core.torrent_data:
            r.update(self.core.torrent_data[info_hash])
        
        data = lt.bencode(r)
        
        # Fire-and-forget write task to avoid blocking the alert loop
        task = self.loop.create_task(self._write_data(p, data, info_hash))
        self.pending_writes.add(task)
        task.add_done_callback(self.pending_writes.discard)

    async def _write_data(self, path: Path, data: bytes, info_hash: str):
        try:
            await self.loop.run_in_executor(None, path.write_bytes, data)
        except Exception as e:
            log.error(f"Failed to write resume data for {info_hash}: {e}")
        finally:
            if info_hash in self.resume_data_futures:
                self.resume_data_futures.pop(info_hash).set_result(True)

    async def on_save_resume_data_failed_alert(self, alert):
        log.error(
            f"Error saving resume_data for torrent {alert.torrent_name} "
            f"error: {alert.error.message()}"
        )
        info_hash = str(alert.handle.info_hash())
        if info_hash in self.resume_data_futures:
            # We don't really care if this fails right now, maybe in the future
            # we should raise an exception.
            self.resume_data_futures.pop(info_hash).set_result(True)

    def save_torrent(self, torrent_handle):
        info_hash = str(torrent_handle.info_hash())
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
        for torrent in self.core.session.get_torrents():
            if torrent.need_save_resume_data():
                self.save_torrent(torrent)
        try:
            await asyncio.wait_for(
                asyncio.gather(*list(self.resume_data_futures.values())), timeout=30.0
            )

        except asyncio.TimeoutError:
            log.warning("Timed out waiting for resume data to save")
        except Exception as e:
            log.error(f"Error saving resume data: {e}")

    def delete(self, info_hash):
        p = Path(self.core.state_dir, info_hash + ".resume")
        if p.is_file():
            p.unlink()

    async def load(self):
        log.info(f"Loading resume data from {self.core.state_dir}")
        for f in self.core.state_dir.iterdir():
            if f.suffix == ".resume":
                log.info(f"Found {f.name}, attempting add..")
                b = f.read_bytes()
                atp = lt.read_resume_data(b)
                try:
                    handle = await asyncio.get_event_loop().run_in_executor(
                        None, functools.partial(self.core.session.add_torrent), atp
                    )
                except RuntimeError as e:
                    log.error(f"Error loading resume data {f}: {e}")
                    continue

                d = lt.bdecode(b)

                # Use the verify handle info_hash as libtorrent 2.0+ might save a different
                # hash in the resume data (e.g. v2 vs v1).
                info_hash = str(handle.info_hash())
                self.core.torrent_data[info_hash] = {}
                for key, value in d.items():
                    if key.startswith(b"spritzle."):
                        self.core.torrent_data[info_hash][key.decode()] = value
