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
