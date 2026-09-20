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
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, Iterator, Optional, Union

import tomlkit
from tomlkit.toml_document import TOMLDocument

log = logging.getLogger("spritzle.cli")

CLI_DEFAULTS: Dict[str, Any] = {
    "color": None,
    "plain": False,
    "theme": "modern",
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
    """Configuration store for Spritzle CLI backed by cli.toml."""

    def __init__(
        self,
        config_dir: Union[Path, str, None] = None,
        filename: str = "cli.toml",
        defaults: Optional[Dict[str, Any]] = None,
    ):
        if config_dir is None:
            env_config = os.environ.get("SPRITZLE_CONFIG") or os.environ.get("SPRITZLE_CONFIG_DIR")
            if env_config:
                self.config_dir = Path(env_config)
            else:
                self.config_dir = Path(Path.home(), ".config", "spritzle")
        else:
            self.config_dir = Path(config_dir)

        self.filename = filename
        self.config_file = Path(self.config_dir, self.filename)
        self.defaults = dict(CLI_DEFAULTS if defaults is None else defaults)
        self._doc: TOMLDocument = tomlkit.document()
        self._unparseable = False
        self.load()

    def load(self) -> None:
        """Load configuration from disk if present."""
        if self.config_file.exists():
            try:
                with self.config_file.open("r", encoding="utf-8") as f:
                    content = f.read()
                    self._doc = tomlkit.parse(content)
                self._unparseable = False
            except Exception as e:
                log.warning(f"Failed to parse CLI config file '{self.config_file}': {e}")
                self._doc = tomlkit.document()
                self._unparseable = True
        else:
            self._doc = tomlkit.document()
            self._unparseable = False

    def save(self) -> None:
        """Atomically persist current configuration to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self._unparseable and self.config_file.exists():
            backup_file = self.config_file.with_suffix(f"{self.config_file.suffix}.bak")
            try:
                shutil.copy2(self.config_file, backup_file)
                log.warning(
                    f"Created backup of unparseable CLI config '{self.config_file}' -> '{backup_file}'"
                )
            except OSError as e:
                log.error(f"Failed to create backup of unparseable CLI config '{self.config_file}': {e}")
            self._unparseable = False

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

    def __contains__(self, key: object) -> bool:
        return key in self.defaults or key in self._doc

    def __iter__(self) -> Iterator[str]:
        keys = set(self.defaults.keys())
        keys.update(self._doc.keys())
        return iter(sorted(keys))

    def __len__(self) -> int:
        keys = set(self.defaults.keys())
        keys.update(self._doc.keys())
        return len(keys)


class RemotesConfig:
    """Stores and manages remote Spritzle daemons in remotes.toml."""

    def __init__(
        self,
        config_dir: Union[Path, str, None] = None,
        filename: str = "remotes.toml",
    ):
        if config_dir is None:
            env_config = os.environ.get("SPRITZLE_CONFIG") or os.environ.get("SPRITZLE_CONFIG_DIR")
            if env_config:
                self.config_dir = Path(env_config)
            else:
                self.config_dir = Path(Path.home(), ".config", "spritzle")
        else:
            self.config_dir = Path(config_dir)

        self.filename = filename
        self.config_file = Path(self.config_dir, self.filename)
        self._doc: TOMLDocument = tomlkit.document()
        self._unparseable = False
        self.load()

    def load(self) -> None:
        """Load configuration from disk if present."""
        if self.config_file.exists():
            try:
                with self.config_file.open("r", encoding="utf-8") as f:
                    content = f.read()
                    self._doc = tomlkit.parse(content)
                self._unparseable = False
            except Exception as e:
                log.warning(f"Failed to parse remotes config file '{self.config_file}': {e}")
                self._doc = tomlkit.document()
                self._unparseable = True
        else:
            self._doc = tomlkit.document()
            self._unparseable = False

    def save(self) -> None:
        """Atomically persist current remotes to disk with 0600 permissions."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self._unparseable and self.config_file.exists():
            backup_file = self.config_file.with_suffix(f"{self.config_file.suffix}.bak")
            try:
                shutil.copy2(self.config_file, backup_file)
                log.warning(
                    f"Created backup of unparseable remotes config '{self.config_file}' -> '{backup_file}'"
                )
            except OSError as e:
                log.error(f"Failed to create backup of unparseable remotes config '{self.config_file}': {e}")
            self._unparseable = False

        temp_file = self.config_file.with_name(f".{self.filename}.tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(self._doc))
        try:
            os.chmod(temp_file, 0o600)
        except OSError:
            pass
        temp_file.replace(self.config_file)

    def get_remotes(self) -> Dict[str, Dict[str, Any]]:
        remotes = self._doc.get("remotes", {})
        if isinstance(remotes, dict):
            return {k: unwrap_toml_value(v) for k, v in remotes.items() if isinstance(v, dict)}
        return {}

    def get_remote(self, name: str) -> Optional[Dict[str, Any]]:
        remotes = self.get_remotes()
        return remotes.get(name)

    def set_remote(
        self,
        name: str,
        url: str,
        daemon_id: str,
        key: str,
        insecure: bool = False,
        ca_cert: Optional[str] = None,
        fingerprint: Optional[str] = None,
    ) -> None:
        if "remotes" not in self._doc or not isinstance(self._doc["remotes"], dict):
            self._doc["remotes"] = tomlkit.table()
        remote_tbl = tomlkit.table()
        remote_tbl["url"] = url
        remote_tbl["daemon_id"] = daemon_id
        remote_tbl["key"] = key
        if insecure:
            remote_tbl["insecure"] = True
        if ca_cert:
            remote_tbl["ca_cert"] = str(ca_cert)
        if fingerprint:
            remote_tbl["fingerprint"] = str(fingerprint)
        self._doc["remotes"][name] = remote_tbl
        self.save()

    def remove_remote(self, name: str) -> bool:
        if "remotes" in self._doc and isinstance(self._doc["remotes"], dict):
            if name in self._doc["remotes"]:
                del self._doc["remotes"][name]
                if self.get_default_remote() == name:
                    if "default_remote" in self._doc:
                        del self._doc["default_remote"]
                self.save()
                return True
        return False

    def get_default_remote(self) -> Optional[str]:
        if "default_remote" in self._doc:
            return str(self._doc["default_remote"])
        return None

    def set_default_remote(self, name: str) -> None:
        self._doc["default_remote"] = name
        self.save()

    def ensure_local_remote(self, state_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """
        Auto-discovers local daemon configuration and keeps 'local' remote updated.
        """
        env_state_dir = os.environ.get("SPRITZLE_STATE_DIR")
        s_dir = state_dir or (Path(env_state_dir) if env_state_dir else (Path.home() / ".local" / "share" / "spritzle" / "state"))
        local_file = Path(s_dir) / "local_remote.json"
        if local_file.exists():
            try:
                with local_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "url" in data and "daemon_id" in data and "api_key" in data:
                    existing = self.get_remote("local")
                    if (
                        not existing
                        or existing.get("daemon_id") != data["daemon_id"]
                        or existing.get("url") != data["url"]
                        or existing.get("key") != data["api_key"]
                    ):
                        self.set_remote("local", data["url"], data["daemon_id"], data["api_key"])
                        if not self.get_default_remote():
                            self.set_default_remote("local")
                    return self.get_remote("local")
            except Exception:
                pass
        return self.get_remote("local")

