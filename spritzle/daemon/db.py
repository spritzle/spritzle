#
# spritzle/db.py
#
# Copyright (C) 2023 Andrew Resch <andrewresch@gmail.com>
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
from typing import Any, Dict, Optional, Iterator, TypeVar

T = TypeVar("T")

TABLE = """
CREATE TABLE IF NOT EXISTS t(
    key TEXT NOT NULL UNIQUE,
    value JSON,
    is_default BOOLEAN CHECK(is_default IN (0, 1))
)
"""


def convert_json(data: bytes) -> Any:
    """Convert JSON bytes to Python object."""
    return json.loads(data)


class DB(collections.abc.MutableMapping[str, Any]):
    """A SQLite-based key-value store with JSON values.

    This class implements a dict-like interface for storing JSON-serializable values
    in a SQLite database. It supports default values and in-memory operation.

    Args:
        path: Path to the SQLite database file
        defaults: Dictionary of default key-value pairs
        in_memory: If True, use an in-memory database
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        defaults: Optional[Dict[str, Any]] = None,
        in_memory: bool = False,
    ):
        sqlite3.register_converter("JSON", convert_json)

        self.path = path
        self.in_memory = in_memory

        self.defaults = defaults if defaults else {}
        self.conn: Optional[sqlite3.Connection] = None

        if self.in_memory:
            self.conn = sqlite3.connect(
                ":memory:", detect_types=sqlite3.PARSE_DECLTYPES
            )
        else:
            if not path:
                raise ValueError(
                    "path must be provided when not using in-memory database"
                )
            self.conn = sqlite3.connect(str(path), detect_types=sqlite3.PARSE_DECLTYPES)

        self.create_table()

    def create_table(self) -> None:
        """Create the database table and insert default values."""
        try:
            self.conn.execute(TABLE)
            for key, value in self.defaults.items():
                self.conn.execute(
                    "INSERT OR IGNORE INTO t(key, value, is_default) VALUES(?, ?, 1)",
                    (key, json.dumps(value)),
                )
            self.conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to create table: {e}") from e

    def reset(self) -> None:
        """Reset the database by dropping and recreating the table."""
        try:
            self.conn.execute("DROP TABLE t")
            self.create_table()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to reset database: {e}") from e

    def __enter__(self) -> "DB":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __del__(self) -> None:
        """Destructor to ensure connection is closed."""
        self.close()

    def __len__(self) -> int:
        """Return the number of items in the database."""
        try:
            return self.conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to get database length: {e}") from e

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the database keys."""
        try:
            cursor = self.conn.execute("SELECT key FROM t")
            for row in cursor:
                yield row[0]
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to iterate database: {e}") from e

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a key-value pair in the database."""
        try:
            self.conn.execute(
                "REPLACE INTO t(key, value, is_default) values(?, ?, 0)",
                (key, json.dumps(value)),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to set item: {e}") from e
        except (TypeError, ValueError) as e:
            raise ValueError(f"Value is not JSON serializable: {e}") from e


    def __getitem__(self, key: str) -> Any:
        """Get a value from the database by key."""
        try:
            value = self.conn.execute(
                "SELECT value FROM t WHERE key=?", (key,)
            ).fetchone()
            if value is None:
                raise KeyError(f"Table key {key} not found.")
            return value[0]
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to get item: {e}") from e

    def __delitem__(self, key: str) -> None:
        """Delete a key from the database or reset to default value."""
        try:
            if key in self.defaults:
                self.conn.execute(
                    "REPLACE INTO t(key, value, is_default) values(?, ?, 1)",
                    (key, json.dumps(self.defaults[key])),
                )
            else:
                cursor = self.conn.execute("DELETE FROM t WHERE key=?", (key,))
                if cursor.rowcount == 0:
                    raise KeyError(f"Table key {key} not found.")
            self.conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to delete item: {e}") from e


    def __contains__(self, key: object) -> bool:
        """Check if a key exists in the database."""
        if not isinstance(key, str):
            return False
        try:
            return bool(
                self.conn.execute("SELECT 1 FROM t WHERE key=?", (key,)).fetchone()
            )
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to check key existence: {e}") from e
