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

from asynctest import patch
import libtorrent as lt
import pytest

from .common import resume_data_dir


async def test_load(core):
    info_hash = '44a040be6d74d8d290cd20128788864cbf770719'
    shutil.copy(resume_data_dir / f'{info_hash}.resume', core.state_dir)
    await core.start()
    torrents = core.session.get_torrents()
    assert len(torrents) == 1
    assert torrents[0].status().name == 'tmprandomfile'
    await core.stop()


async def test_new_torrent_saved(cli, core):
    assert len(list(core.state_dir.iterdir())) == 0
    torrent_address = str(cli.make_url('/test_torrents/random_one_file.torrent'))
    info_hash = '44a040be6d74d8d290cd20128788864cbf770719'
    await cli.post('/torrent', json={'url': torrent_address})
    with open(core.state_dir / f'{info_hash}.resume', mode='rb') as f:
        data = lt.bdecode(f.read())
        assert b'paused' in data
        assert data[b'info'][b'length'] == 4194304


async def test_resume_data_deleted(cli, core):
    info_hash = '44a040be6d74d8d290cd20128788864cbf770719'
    resume_file = core.state_dir / f'{info_hash}.resume'
    torrent_address = str(cli.make_url('/test_torrents/random_one_file.torrent'))
    await cli.post('/torrent', json={'url': torrent_address})
    assert resume_file.is_file()
    await cli.delete(f'/torrent/{info_hash}')
    assert not resume_file.is_file()


@pytest.mark.parametrize('frequency', [0.1, 0.2])
async def test_resume_data_save_loop(core, frequency):
    """
    Verifies save resume data is called, and called as often as specified in config.
    """
    core_run_time = 0.61
    expected_runs = int(core_run_time / frequency)
    core.config['resume_data_save_frequency'] = frequency
    with patch('spritzle.daemon.resume_data.ResumeData.save_all') as mock_save:
        await core.start()
        await asyncio.sleep(core_run_time)
        # Allow a bit of slop so the test isn't so fragile
        assert expected_runs - 1 <= mock_save.call_count <= expected_runs + 1
        await core.stop()
