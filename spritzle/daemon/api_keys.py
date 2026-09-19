#
# spritzle/daemon/api_keys.py
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

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
from typing import Any, Dict, List, Optional, Tuple, Union


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


class KeyManager:
    """Manages API keys and local client discovery on the daemon."""

    def __init__(self, state_dir: Union[Path, str]):
        self.state_dir = Path(state_dir)
        self.keys_file = self.state_dir / "keys.json"
        self.local_remote_file = self.state_dir / "local_remote.json"
        self._keys: Dict[str, Dict[str, Any]] = self._load_keys()

    def _load_keys(self) -> Dict[str, Dict[str, Any]]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if self.keys_file.exists():
            try:
                with self.keys_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_keys(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        temp_file = self.keys_file.with_suffix(".tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(self._keys, f, indent=2)
        try:
            os.chmod(temp_file, 0o600)
        except OSError:
            pass
        temp_file.replace(self.keys_file)

    def create_key(self, name: str = "") -> Tuple[str, Dict[str, Any]]:
        """
        Creates a new API key. Returns (raw_key, metadata).
        The raw_key is only returned here and is not stored in keys.json.
        """
        raw_key = f"spritzle_{secrets.token_hex(16)}"
        key_id = f"key_{secrets.token_hex(8)}"
        created_at = datetime.now(timezone.utc).isoformat()
        prefix = raw_key[:13]  # e.g. "spritzle_8f3a"

        key_data = {
            "id": key_id,
            "name": name or "unnamed",
            "prefix": prefix,
            "hash": hash_key(raw_key),
            "created_at": created_at,
            "is_active": True,
        }
        self._keys[key_id] = key_data
        self._save_keys()

        safe_metadata = {k: v for k, v in key_data.items() if k != "hash"}
        return raw_key, safe_metadata

    def verify_key(self, raw_key: str) -> Optional[Dict[str, Any]]:
        """
        Verifies a raw API key against stored active hashes.
        Returns the key metadata (without hash) if valid and active, else None.
        """
        if not raw_key:
            return None
        candidate_hash = hash_key(raw_key)

        matched_key: Optional[Dict[str, Any]] = None
        for key_data in self._keys.values():
            stored_hash = key_data.get("hash", "")
            if secrets.compare_digest(candidate_hash, stored_hash):
                if key_data.get("is_active", True):
                    matched_key = {k: v for k, v in key_data.items() if k != "hash"}
                    break
        return matched_key

    def revoke_key(self, id_or_name: str) -> bool:
        """
        Revokes a key by its ID or name. Returns True if a key was revoked.
        """
        target_id: Optional[str] = None
        if id_or_name in self._keys:
            target_id = id_or_name
        else:
            for k_id, k_val in self._keys.items():
                if k_val.get("name") == id_or_name and k_val.get("is_active", True):
                    target_id = k_id
                    break

        if target_id and target_id in self._keys:
            self._keys[target_id]["is_active"] = False
            self._save_keys()
            return True
        return False

    def list_keys(self) -> List[Dict[str, Any]]:
        """Returns list of all keys with metadata, omitting the hash."""
        return [{k: v for k, v in item.items() if k != "hash"} for item in self._keys.values()]

    def ensure_local_client_remote(self, daemon_url: str, daemon_id: str) -> Dict[str, Any]:
        """
        Ensures a local client discovery file exists with a valid API key.
        """
        if self.local_remote_file.exists():
            try:
                with self.local_remote_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if (
                    isinstance(data, dict)
                    and data.get("daemon_id") == daemon_id
                    and self.verify_key(data.get("api_key", "")) is not None
                ):
                    data["url"] = daemon_url
                    temp_file = self.local_remote_file.with_suffix(".tmp")
                    with temp_file.open("w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    try:
                        os.chmod(temp_file, 0o600)
                    except OSError:
                        pass
                    temp_file.replace(self.local_remote_file)
                    return data
            except (json.JSONDecodeError, OSError):
                pass

        raw_key, meta = self.create_key(name="local_client")
        remote_data = {
            "name": "local",
            "url": daemon_url,
            "daemon_id": daemon_id,
            "api_key": raw_key,
        }
        temp_file = self.local_remote_file.with_suffix(".tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(remote_data, f, indent=2)
        try:
            os.chmod(temp_file, 0o600)
        except OSError:
            pass
        temp_file.replace(self.local_remote_file)
        return remote_data
