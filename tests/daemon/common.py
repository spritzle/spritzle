#
# tests/common.py
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

from pathlib import Path
from typing import Any
import libtorrent as lt

resume_data_dir = Path(__file__).resolve().parent / "resume_data"
torrent_dir = Path(__file__).resolve().parent / "torrents"


def add_test_torrent(session: Any, ti: Any, save_path: str = "/tmp", **kwargs: Any) -> Any:
    atp = lt.add_torrent_params()
    atp.ti = ti
    atp.save_path = save_path
    for k, v in kwargs.items():
        setattr(atp, k, v)
    return session.add_torrent(atp)
