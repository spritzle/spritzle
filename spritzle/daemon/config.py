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

import collections.abc
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict

DEFAULTS = {
    "add_torrent_params.save_path": "",
    "auth_password": "password",
    "auth_secret": "",
    "auth_timeout": 120,
    "auth_allow_hosts": ["127.0.0.1"],
    "resume_data_save_frequency": 60,
}

CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS config(
    key TEXT NOT NULL UNIQUE,
    value JSON,
    is_default BOOLEAN CHECK(is_default IN (0, 1))
)
"""


def convert_json(data: bytes) -> Any:
    return json.loads(data)


class Config(collections.abc.MutableMapping):
    def __init__(
        self,
        filename: str = "config.db",
        config_dir: Path = None,
        defaults: Dict[str, Any] = DEFAULTS,
        in_memory: bool = False,
    ):

        sqlite3.register_converter("JSON", convert_json)

        self.iter_cursor = None
        self.in_memory = in_memory
        self.defaults = defaults

        if config_dir is None:
            self.path = Path(Path.home(), ".config", "spritzle")
        else:
            self.path = Path(config_dir)

        if self.in_memory:
            self.conn = sqlite3.connect(
                ":memory:", detect_types=sqlite3.PARSE_DECLTYPES
            )
        else:
            self.config_file = Path(self.path, filename)
            self.path.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(
                self.config_file, detect_types=sqlite3.PARSE_DECLTYPES
            )

        self.create_config_table()

    def create_config_table(self):
        self.conn.execute(CONFIG_TABLE)
        for key, value in self.defaults.items():
            self.conn.execute(
                "INSERT OR IGNORE INTO config(key, value, is_default) VALUES(?, ?, 1)",
                (key, json.dumps(value)),
            )
        self.conn.commit()

    def reset(self):
        self.conn.execute("DROP TABLE config")
        self.create_config_table()

    def __del__(self):
        self.conn.close()

    def __len__(self):
        return self.conn.execute("SELECT COUNT(*) FROM config").fetchone()[0]

    def __iter__(self):
        return self

    def __next__(self):
        if self.iter_cursor is None:
            self.iter_cursor = self.conn.execute("SELECT key FROM config")
        try:
            return next(self.iter_cursor)[0]
        except StopIteration as e:
            self.iter_cursor = None
            raise e

    def __setitem__(self, key: str, value: Any):
        self.conn.execute(
            "REPLACE INTO config(key, value, is_default) values(?, ?, 0)",
            (key, json.dumps(value)),
        )
        self.conn.commit()

    def __getitem__(self, key: str):
        value = self.conn.execute(
            "SELECT value FROM config WHERE key=?", (key,)
        ).fetchone()
        if value is None:
            raise KeyError(f"Config key {key} not found.")

        return value[0]

    def __delitem__(self, key: str):
        # Set the default value if it exists instead of removing the row, otherwise just remove the row
        if key in self.defaults:
            self.conn.execute(
                "REPLACE INTO config(key, value, is_default) values(?, ?, 1)",
                (key, self.defaults[key]),
            )
        else:
            self.conn.execute("DELETE FROM config WHERE key=?", (key,))
        self.conn.commit()
