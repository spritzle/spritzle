#
# spritzle/config.py
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
from typing import Any, Dict, Union

from spritzle.daemon.db import DB

DEFAULTS = {
    "add_torrent_params.save_path": ".",
    "auth_password": "password",
    "auth_secret": "",
    "auth_timeout": 120,
    "auth_allow_hosts": ["127.0.0.1"],
    "resume_data_save_frequency": 60,
}


class Config(DB):
    path: Path

    def __init__(
        self,
        filename: str = "config.db",
        config_dir: Union[Path, str, None] = None,
        defaults: Dict[str, Any] = DEFAULTS,
        in_memory: bool = False,
    ):
        if config_dir is None:
            self.config_dir = Path(Path.home(), ".config", "spritzle")
        else:
            self.config_dir = Path(config_dir)

        if not in_memory:
            self.config_file = Path(self.config_dir, filename)
            self.config_dir.mkdir(parents=True, exist_ok=True)
            file_path = self.config_file
        else:
            # When in_memory, we don't have a config *file*, but directory might still be relevant
            self.config_file = None
            file_path = None

        super().__init__(path=file_path, defaults=defaults, in_memory=in_memory)

        # Alias for backward compatibility if consumers use config.path as directory
        # We set this AFTER super().__init__ because DB.__init__ overwrites self.path with the file path
        # (or None if in_memory). Config expects self.path to be the directory.
        self.path = self.config_dir
