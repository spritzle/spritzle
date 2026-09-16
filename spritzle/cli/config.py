#
# spritzle/cli/config.py
#
# Copyright (C) 2026 Andrew Resch <andrewresch@gmail.com>
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
import os
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Union

import tomlkit
from tomlkit.toml_document import TOMLDocument

CLI_DEFAULTS: Dict[str, Any] = {
    "host": "127.0.0.1",
    "port": 8080,
    "token": "",
    "color": None,
    "plain": False,
}


def coerce_config_value(raw: str) -> Any:
    """Coerce string representation into appropriate Python type."""
    normalized = raw.strip()
    lower = normalized.lower()
    if lower in ("true", "yes", "on"):
        return True
    if lower in ("false", "no", "off"):
        return False
    if lower in ("none", "null"):
        return None

    # Try integer
    try:
        return int(normalized)
    except ValueError:
        pass

    # Try float
    try:
        return float(normalized)
    except ValueError:
        pass

    # Try JSON / TOML structure (lists, dicts)
    try:
        return json.loads(normalized)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    return normalized


def unwrap_toml_value(val: Any) -> Any:
    """Unwrap tomlkit primitive types into standard Python primitives."""
    if hasattr(val, "unwrap"):
        return val.unwrap()
    return val


class CLIConfig(collections.abc.MutableMapping[str, Any]):
    """Configuration store for Spritzle CLI backed by a TOML file."""

    def __init__(
        self,
        config_dir: Union[Path, str, None] = None,
        filename: str = "cli.toml",
        defaults: Optional[Dict[str, Any]] = None,
    ):
        if config_dir is None:
            self.config_dir = Path(Path.home(), ".config", "spritzle")
        else:
            self.config_dir = Path(config_dir)

        self.filename = filename
        self.config_file = Path(self.config_dir, self.filename)
        self.defaults = dict(CLI_DEFAULTS if defaults is None else defaults)
        self._doc: TOMLDocument = tomlkit.document()
        self.load()

    def load(self) -> None:
        """Load configuration from disk if present."""
        if self.config_file.exists():
            try:
                with self.config_file.open("r", encoding="utf-8") as f:
                    content = f.read()
                    self._doc = tomlkit.parse(content)
            except Exception:
                # If unparseable, start with a fresh document
                self._doc = tomlkit.document()
        else:
            self._doc = tomlkit.document()

    def save(self) -> None:
        """Atomically persist current configuration to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        temp_file = self.config_file.with_name(f".{self.filename}.tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(self._doc))
        try:
            os.chmod(temp_file, 0o600)
        except OSError:
            pass
        temp_file.replace(self.config_file)

    def is_modified(self, key: str) -> bool:
        """Check whether a key differs from or is explicitly set in file overrides."""
        return key in self._doc

    def unset(self, key: str) -> bool:
        """Remove an explicit configuration override."""
        if key in self._doc:
            del self._doc[key]
            self.save()
            return True
        return False

    def reset(self) -> None:
        """Reset all configuration overrides back to defaults."""
        self._doc = tomlkit.document()
        if self.config_file.exists():
            try:
                self.config_file.unlink()
            except OSError:
                self.save()

    def as_dict(self) -> Dict[str, Any]:
        """Return merged configuration dictionary containing all keys and defaults."""
        result: Dict[str, Any] = {}
        for k in self:
            result[k] = self[k]
        return result

    def __getitem__(self, key: str) -> Any:
        if key in self._doc:
            return unwrap_toml_value(self._doc[key])
        if key in self.defaults:
            return self.defaults[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self._doc[key] = value
        self.save()

    def __delitem__(self, key: str) -> None:
        if key in self._doc:
            del self._doc[key]
            self.save()
        else:
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        keys = set(self.defaults.keys())
        keys.update(self._doc.keys())
        return iter(sorted(keys))

    def __len__(self) -> int:
        keys = set(self.defaults.keys())
        keys.update(self._doc.keys())
        return len(keys)
