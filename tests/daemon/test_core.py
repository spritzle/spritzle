#
# test_core.py
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
import libtorrent as lt


async def test_save_session_state(core):
    state_file = core.state_dir / "session.state"
    await core.start()
    assert not state_file.is_file()
    await core.save_session_state()
    assert state_file.is_file()
    with state_file.open(mode="rb") as f:
        data = lt.bdecode(f.read())
        assert b"settings" in data


async def test_torrent_data(cli, core):
    info_hash = "44a040be6d74d8d290cd20128788864cbf770719"
    torrent_address = str(cli.make_url("/test_torrents/random_one_file.torrent"))
    assert not core.torrent_data
    await cli.post("/torrent", json={"url": torrent_address})
    assert info_hash in core.torrent_data
    await cli.delete("/torrent/44a040be6d74d8d290cd20128788864cbf770719")
    assert not core.torrent_data


def test_get_default_settings(core):
    settings = core.get_default_settings()
    assert isinstance(settings, dict)
    assert "alert_mask" in settings
    assert "user_agent" in settings
    assert "Spritzle/" in settings["user_agent"]
    assert "libtorrent/" in settings["user_agent"]


async def test_start_stop(core):
    assert core.session is None
    await core.start()
    assert core.session is not None
    assert core.alert.session is not None
    await core.stop()
    assert core.session is None


async def test_get_session_stats(core):
    await core.start()

    # Trigger an unsolicited stats alert to simulate a periodic update or race condition.
    # If the bug is present, this will cause the alert loop to crash because
    # session_stats_future will be None.
    core.session.post_session_stats()
    await asyncio.sleep(0.1)

    stats = await core.get_session_stats()
    assert isinstance(stats, dict)
    assert len(stats) > 0
    # ensure subsequent calls also work
    stats2 = await core.get_session_stats()
    assert isinstance(stats2, dict)
    assert len(stats2) > 0
    await core.stop()


async def test_alert_loop_robustness(core):
    await core.start()

    # Register a handler that crashes
    async def crashing_handler(alert):
        raise RuntimeError("Oops -> Crash Handler")

    # We attach it to stats_alert since we can easily trigger that
    core.alert.register_handler("session_stats_alert", crashing_handler)

    # Trigger the alert
    core.session.post_session_stats()
    # Allow loop to process and crash
    await asyncio.sleep(0.1)

    # Now verify the loop is still running by performing a valid operation that requires alerts
    # If the loop crashed, this will hang (and eventually timeout via wait_for in a real scenario,
    # or just hang if we don't wrap it. Pytest usually timeouts eventually but let's be explicit if we want).
    # Since we fixed the "unexpected stats alert" bug in the previous step,
    # get_session_stats() should work IF the loop is still alive.
    stats = await core.get_session_stats()
    assert isinstance(stats, dict)

    await core.stop()
