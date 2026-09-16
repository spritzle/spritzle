#
# test_resume_data.py
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
import shutil
from unittest.mock import patch

import libtorrent as lt
import pytest

from spritzle.daemon.core import Core
from .common import resume_data_dir


async def test_load(core):
    info_hash = "44a040be6d74d8d290cd20128788864cbf770719"
    shutil.copy(resume_data_dir / f"{info_hash}.resume", core.state_dir)
    await core.start()
    torrents = core.session.get_torrents()
    assert len(torrents) == 1
    assert torrents[0].status().name == "tmprandomfile"
    await core.stop()


async def test_new_torrent_saved(cli, core):
    assert len(list(core.state_dir.iterdir())) == 0
    torrent_address = str(cli.make_url("/test_torrents/random_one_file.torrent"))
    info_hash = "44a040be6d74d8d290cd20128788864cbf770719"
    await cli.post("/torrent", json={"url": torrent_address})
    with open(core.state_dir / f"{info_hash}.resume", mode="rb") as f:
        data = lt.bdecode(f.read())
        assert b"paused" in data
        assert data[b"info"][b"length"] == 4_194_304


async def test_resume_data_deleted(cli, core):
    info_hash = "44a040be6d74d8d290cd20128788864cbf770719"
    resume_file = core.state_dir / f"{info_hash}.resume"
    torrent_address = str(cli.make_url("/test_torrents/random_one_file.torrent"))
    await cli.post("/torrent", json={"url": torrent_address})
    assert resume_file.is_file()
    await cli.delete(f"/torrent/{info_hash}")
    assert not resume_file.is_file()


@pytest.mark.parametrize("interval", [0.1, 0.2])
async def test_resume_data_save_loop(core, interval):
    """
    Verifies save resume data is called, and called as often as specified in config.
    """
    core_run_time = 0.61
    expected_runs = int(core_run_time / interval)
    core.config["save_resume_data_interval"] = interval
    with patch("spritzle.daemon.resume_data.ResumeData.save_all") as mock_save:
        await core.start()
        await asyncio.sleep(core_run_time)
        # Allow a bit of slop so the test isn't so fragile
        assert expected_runs - 1 <= mock_save.call_count <= expected_runs + 1
        await core.stop()


async def test_load_custom_metadata_types(cli, core):
    """
    Verifies that custom metadata (e.g. spritzle.tags) loaded from resume data
    are deserialized as str instances rather than bytes, ensuring JSON serialization
    and hook alerts work correctly after restart.
    """
    torrent_address = str(cli.make_url("/test_torrents/random_one_file.torrent"))
    info_hash = "44a040be6d74d8d290cd20128788864cbf770719"
    resp = await cli.post(
        "/torrent",
        json={"url": torrent_address, "spritzle.tags": ["linux", "iso"]},
    )
    assert resp.status == 201
    assert core.torrent_data[info_hash]["spritzle.tags"] == ["linux", "iso"]

    state_dir = core.state_dir
    config = core.config

    # Save resume data and stop core
    await core.stop()

    # Restart core from the same state_dir, mimicking a new daemon process
    settings = {
        "enable_upnp": False,
        "enable_natpmp": False,
        "enable_lsd": False,
        "enable_dht": False,
        "anonymous_mode": True,
        "alert_mask": 0,
        "stop_tracker_timeout": 0,
    }
    new_core = Core(config, state_dir)
    await new_core.start(settings)
    from spritzle.daemon.keys import APP_KEY_CORE
    cli.app[APP_KEY_CORE] = new_core

    try:
        # The metadata in torrent_data must contain python strings, not bytes
        tags = new_core.torrent_data[info_hash].get("spritzle.tags")
        assert tags == ["linux", "iso"]
        assert all(isinstance(tag, str) for tag in tags)

        # Calling GET /torrent/{info_hash} must return 200 JSON, not 500 TypeError
        resp = await cli.get(f"/torrent/{info_hash}")
        assert resp.status == 200
        data = await resp.json()
        assert data["spritzle.tags"] == ["linux", "iso"]

        # Hooks join must not raise TypeError
        assert new_core.get_torrent_tags(info_hash) == ["linux", "iso"]
        assert ",".join(new_core.get_torrent_tags(info_hash)) == "linux,iso"
    finally:
        await new_core.stop()


async def test_load_corrupt_resume_data_file(core):
    """
    Verifies that corrupt or 0-byte .resume files do not crash daemon startup,
    and valid resume files in the same directory are still loaded.
    """
    # Copy a valid resume file
    valid_hash = "44a040be6d74d8d290cd20128788864cbf770719"
    shutil.copy(resume_data_dir / f"{valid_hash}.resume", core.state_dir)

    # Create empty and corrupted resume files
    (core.state_dir / "empty.resume").write_bytes(b"")
    (core.state_dir / "garbage.resume").write_bytes(b"invalid bencoded resume content")

    # Starting core must not raise RuntimeError
    await core.start()

    torrents = core.session.get_torrents()
    assert len(torrents) == 1
    assert str(torrents[0].info_hash()) == valid_hash

    await core.stop()


async def test_delete_race_condition_pending_write(core):
    """
    Verifies that if a write is scheduled or in-flight when delete() is called,
    the .resume file is not resurrected and pending writes do not recreate it.
    """
    await core.start()
    info_hash = "44a040be6d74d8d290cd20128788864cbf770719"
    resume_file = core.state_dir / f"{info_hash}.resume"

    # Simulate an in-flight write task
    dummy_data = b"d4:infod6:lengthi1024eee"
    loop = asyncio.get_running_loop()
    write_task = loop.create_task(
        core.resume_data._write_data(resume_file, dummy_data, info_hash)
    )
    core.resume_data.pending_writes.add(write_task)

    # Immediately call delete before write finishes / executor completes
    core.resume_data.delete(info_hash)

    # Wait for pending writes to finish
    await asyncio.gather(*core.resume_data.pending_writes)

    # The file must NOT exist on disk
    assert not resume_file.is_file()

    # Even if an alert arrives for the deleted hash after delete(), it should not write
    class DummyAlert:
        class Handle:
            def info_hash(self):
                return info_hash

        handle = Handle()
        params = {}

    await core.resume_data.on_save_resume_data_alert(DummyAlert())
    if core.resume_data.pending_writes:
        await asyncio.gather(*core.resume_data.pending_writes)

    assert not resume_file.is_file()

    await core.stop()


async def test_save_all_handles_cancelled_futures_and_none_session(core):
    await core.start()

    fut1 = asyncio.Future()
    fut2 = asyncio.Future()
    core.resume_data.resume_data_futures["hash1"] = fut1
    core.resume_data.resume_data_futures["hash2"] = fut2

    async def cancel_later():
        await asyncio.sleep(0.01)
        core.resume_data.delete("hash1")
        fut2.set_result(True)

    asyncio.create_task(cancel_later())

    # save_all() must not propagate CancelledError when fut1 is cancelled during gather
    await core.resume_data.save_all()

    # save_all() when session is None must not raise AttributeError
    core.session = None
    await core.resume_data.save_all()

    await core.stop()


async def test_save_all_timeout_clears_futures(core, monkeypatch):
    await core.start()

    # Create an unresolved future simulating a torrent whose alert never arrives
    unresolved_fut = asyncio.Future()
    core.resume_data.resume_data_futures["stuck_hash"] = unresolved_fut

    # Patch wait_for timeout to be tiny for the test
    real_wait_for = asyncio.wait_for

    async def mock_wait_for(fut, timeout=None):
        return await real_wait_for(fut, timeout=0.02)

    monkeypatch.setattr(asyncio, "wait_for", mock_wait_for)

    await core.resume_data.save_all()

    # Stuck future must be pruned so it doesn't block future saves
    assert "stuck_hash" not in core.resume_data.resume_data_futures
    assert unresolved_fut.cancelled() or unresolved_fut.done()

    await core.stop()


async def test_write_data_does_not_pop_newer_future(core, tmp_path):
    await core.start()

    info_hash = "testhash123"
    old_fut = asyncio.Future()
    new_fut = asyncio.Future()

    core.resume_data.resume_data_futures[info_hash] = old_fut
    dummy_file = tmp_path / f"{info_hash}.resume"

    # Start write task bound to old_fut
    write_task = asyncio.create_task(
        core.resume_data._write_data(dummy_file, b"data", info_hash, old_fut)
    )

    # In the meantime, simulate a new save_torrent registering a new future
    core.resume_data.resume_data_futures[info_hash] = new_fut

    await write_task

    # Old future should be completed
    assert old_fut.done() is True
    # New future must NOT have been popped or completed prematurely!
    assert core.resume_data.resume_data_futures.get(info_hash) is new_fut
    assert new_fut.done() is False

    await core.stop()


async def test_resume_data_save_loop_string_interval(core):
    """
    Verifies that save_loop does not crash with TypeError when save_resume_data_interval
    is set as a string (e.g. "0.1").
    """
    core.config["save_resume_data_interval"] = "0.1"
    save_called = asyncio.Event()

    async def mock_save_all():
        save_called.set()

    with patch.object(core.resume_data, "save_all", side_effect=mock_save_all):
        await core.start()
        try:
            await asyncio.wait_for(save_called.wait(), timeout=0.5)
        finally:
            await core.stop()


async def test_save_torrent_multi_waiter_cancellation_isolation(core):
    await core.start()
    info_hash = "44a040be6d74d8d290cd20128788864cbf770719"

    class DummyHandle:
        def info_hash(self):
            return info_hash

        def save_resume_data(self, flags=0):
            pass

    handle = DummyHandle()
    fut1 = core.resume_data.save_torrent(handle)
    fut2 = core.resume_data.save_torrent(handle)

    # In a multi-waiter system, each caller must get its own future
    assert fut1 is not fut2

    # If caller 1 cancels its wait, caller 2 must not be cancelled
    fut1.cancel()
    assert fut1.cancelled()
    assert not fut2.cancelled()

    class DummyAlert:
        class Handle:
            def info_hash(self):
                return info_hash

        handle = Handle()
        params = {}

    await core.resume_data.on_save_resume_data_alert(DummyAlert())
    if core.resume_data.pending_writes:
        await asyncio.gather(*core.resume_data.pending_writes)

    assert fut2.done()
    assert fut2.result() is True
    await core.stop()








