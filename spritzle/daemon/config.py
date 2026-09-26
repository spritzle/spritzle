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
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Callable, Dict, Iterator, Optional, Union

import tomlkit
from tomlkit.items import Table
from tomlkit.toml_document import TOMLDocument

log = logging.getLogger("spritzle")

def get_default_save_path() -> str:
    env_path = os.environ.get("SPRITZLE_SAVE_PATH") or os.environ.get("SPRITZLE_DOWNLOAD_DIR")
    if env_path:
        return env_path
    try:
        return str(Path.home() / "Downloads")
    except Exception:
        return "/tmp/spritzle-downloads"


DEFAULTS = {
    "default_save_path": get_default_save_path(),
    "save_resume_data_interval": 60,
    "config_watch_interval": 2.0,
    "listen_interfaces": os.environ.get("SPRITZLE_LISTEN_INTERFACES", ""),
    "state_dir": os.environ.get("SPRITZLE_STATE_DIR", ""),
}



def unwrap_toml_value(val: Any) -> Any:
    """Unwrap tomlkit primitive types into standard Python primitives."""
    if hasattr(val, "unwrap"):
        return val.unwrap()
    if isinstance(val, dict):
        return {k: unwrap_toml_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [unwrap_toml_value(v) for v in val]
    return val


def _get_doc_keys(d: Any, prefix: str = "") -> list[str]:
    """Recursively collect dotted key paths from a document/table."""
    keys: list[str] = []
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, (dict, Table)):
            if len(v) == 0:
                keys.append(full_key)
            else:
                keys.extend(_get_doc_keys(v, full_key))
        else:
            keys.append(full_key)
    return keys


class Config(collections.abc.MutableMapping[str, Any]):
    """Configuration store for Spritzle daemon backed by a TOML file."""

    path: Path
    config_file: Optional[Path]

    def __init__(
        self,
        filename: str = "daemon.toml",
        config_dir: Union[Path, str, None] = None,
        defaults: Optional[Dict[str, Any]] = None,
        in_memory: bool = False,
    ):
        if config_dir is None:
            self.config_dir = Path(Path.home(), ".config", "spritzle")
        else:
            self.config_dir = Path(config_dir)

        # Retain self.path as config directory for backwards compatibility
        self.path = self.config_dir
        self.filename = filename
        self.defaults = dict(DEFAULTS if defaults is None else defaults)
        self.in_memory = in_memory

        if not in_memory:
            self.config_file = Path(self.config_dir, self.filename)
            self.config_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.config_file = None

        self._doc: TOMLDocument = tomlkit.document()
        self._unparseable = False
        self._last_mtime_ns: Optional[int] = None
        self._change_callbacks: list[Callable[["Config"], None]] = []
        if not self.in_memory and self.config_file is not None:
            if self.config_file.exists():
                self.load()
            else:
                self.save()

    def add_change_callback(self, callback: Callable[["Config"], None]) -> None:
        """Register a callback to be notified when configuration is reloaded or updated."""
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable[["Config"], None]) -> None:
        """Unregister a configuration change callback."""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)

    def _notify_change(self) -> None:
        """Notify all registered callbacks of configuration changes."""
        for cb in list(self._change_callbacks):
            try:
                cb(self)
            except Exception as e:
                log.error(f"Error in config change callback: {e}")

    def load(self) -> None:
        """Load configuration from disk if present."""
        if self.config_file and self.config_file.exists():
            try:
                with self.config_file.open("r", encoding="utf-8") as f:
                    content = f.read()
                    self._doc = tomlkit.parse(content)
                self._unparseable = False
                try:
                    self._last_mtime_ns = self.config_file.stat().st_mtime_ns
                except OSError:
                    self._last_mtime_ns = None
            except Exception as e:
                log.error(f"Failed to parse config file '{self.config_file}': {e}")
                self._doc = tomlkit.document()
                self._unparseable = True
        else:
            self._doc = tomlkit.document()
            self._unparseable = False
            self._last_mtime_ns = None

    def reload(self, force: bool = False) -> bool:
        """Reload configuration from disk.

        Returns True if configuration was reloaded and changed, False otherwise.
        If the file cannot be parsed or read, retains existing configuration and returns False.
        """
        if self.in_memory or self.config_file is None:
            return False
        if not self.config_file.exists():
            return False

        try:
            mtime_ns = self.config_file.stat().st_mtime_ns
        except OSError:
            return False

        if not force and self._last_mtime_ns is not None and mtime_ns == self._last_mtime_ns:
            return False

        try:
            with self.config_file.open("r", encoding="utf-8") as f:
                content = f.read()
            new_doc = tomlkit.parse(content)
        except Exception as e:
            log.error(f"Failed to reload config file '{self.config_file}': {e}")
            return False

        self._doc = new_doc
        self._last_mtime_ns = mtime_ns
        self._unparseable = False
        log.info(f"Reloaded configuration from '{self.config_file}'")
        self._notify_change()
        return True

    def save(self) -> None:
        """Atomically persist current configuration to disk."""
        if self.in_memory or self.config_file is None:
            self._notify_change()
            return
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self._unparseable and self.config_file.exists():
            backup_file = self.config_file.with_suffix(f"{self.config_file.suffix}.bak")
            try:
                shutil.copy2(self.config_file, backup_file)
                log.warning(
                    f"Created backup of unparseable config file '{self.config_file}' -> '{backup_file}'"
                )
            except OSError as e:
                log.error(f"Failed to create backup of unparseable config '{self.config_file}': {e}")
            self._unparseable = False

        temp_file = self.config_file.with_name(f".{self.filename}.tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(self._doc))
        try:
            os.chmod(temp_file, 0o600)
        except OSError:
            pass
        temp_file.replace(self.config_file)
        try:
            self._last_mtime_ns = self.config_file.stat().st_mtime_ns
        except OSError:
            self._last_mtime_ns = None
        self._notify_change()

    def reset(self) -> None:
        """Reset all configuration overrides back to defaults."""
        self._doc = tomlkit.document()
        if not self.in_memory and self.config_file and self.config_file.exists():
            try:
                self.config_file.unlink()
            except OSError:
                self.save()

    def snapshot(self) -> TOMLDocument:
        """Return a deep copy of the explicit configuration document."""
        return tomlkit.parse(tomlkit.dumps(self._doc))

    def restore(self, snapshot: TOMLDocument) -> None:
        """Restore configuration from a snapshot and persist to disk."""
        self._doc = snapshot
        self.save()

    def as_dict(self) -> Dict[str, Any]:
        """Return merged configuration dictionary containing all keys and defaults."""
        return {k: self[k] for k in self}

    def __enter__(self) -> "Config":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def close(self) -> None:
        pass

    def __getitem__(self, key: str) -> Any:
        if key in self._doc:
            return unwrap_toml_value(self._doc[key])

        if "." in key:
            parts = key.split(".")
            node: Any = self._doc
            found = True
            for part in parts:
                if isinstance(node, (dict, Table)) and part in node:
                    node = node[part]
                else:
                    found = False
                    break
            if found:
                return unwrap_toml_value(node)

        if key in self.defaults:
            return self.defaults[key]

        raise KeyError(f"Table key {key} not found.")

    def __setitem__(self, key: str, value: Any) -> None:
        if "." in key:
            if key in self._doc:
                del self._doc[key]
            parts = key.split(".")
            curr: Any = self._doc
            for part in parts[:-1]:
                if part not in curr or not isinstance(curr[part], (dict, Table)):
                    curr[part] = tomlkit.table()
                curr = curr[part]
            curr[parts[-1]] = value
        else:
            self._doc[key] = value
        self.save()

    def __delitem__(self, key: str) -> None:
        deleted = False
        if key in self._doc:
            del self._doc[key]
            deleted = True
        elif "." in key:
            parts = key.split(".")
            curr: Any = self._doc
            parents: list[tuple[Any, str]] = []
            for part in parts[:-1]:
                if isinstance(curr, (dict, Table)) and part in curr:
                    parents.append((curr, part))
                    curr = curr[part]
                else:
                    break
            else:
                if isinstance(curr, (dict, Table)) and parts[-1] in curr:
                    del curr[parts[-1]]
                    deleted = True
                    for parent, part in reversed(parents):
                        if len(parent[part]) == 0:
                            del parent[part]

        if not deleted:
            if key not in self.defaults:
                raise KeyError(f"Table key {key} not found.")

        self.save()

    def __iter__(self) -> Iterator[str]:
        keys = set(self.defaults.keys())
        keys.update(_get_doc_keys(self._doc))
        return iter(sorted(keys))

    def __len__(self) -> int:
        keys = set(self.defaults.keys())
        keys.update(_get_doc_keys(self._doc))
        return len(keys)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        if key in self._doc:
            return True
        if "." in key:
            parts = key.split(".")
            node: Any = self._doc
            for part in parts:
                if isinstance(node, (dict, Table)) and part in node:
                    node = node[part]
                else:
                    break
            else:
                return True
        return key in self.defaults
