#
# test_config.py
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

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from spritzle.cli.config import (
    CLIConfig,
    RemotesConfig,
    coerce_config_value,
    unwrap_toml_value,
)


def test_coerce_config_value():
    # Booleans
    assert coerce_config_value("true") is True
    assert coerce_config_value("True") is True
    assert coerce_config_value("YES") is True
    assert coerce_config_value("on") is True
    assert coerce_config_value("false") is False
    assert coerce_config_value("No") is False
    assert coerce_config_value("OFF") is False

    # None / null
    assert coerce_config_value("none") is None
    assert coerce_config_value("null") is None
    assert coerce_config_value("NULL") is None

    # Integers
    assert coerce_config_value("42") == 42
    assert coerce_config_value("-10") == -10
    assert coerce_config_value("0") == 0

    # Floats
    assert coerce_config_value("3.14") == 3.14
    assert coerce_config_value("-0.5") == -0.5

    # JSON structures
    assert coerce_config_value('["a", "b", 1]') == ["a", "b", 1]
    assert coerce_config_value('{"key": "value"}') == {"key": "value"}

    # Strings
    assert coerce_config_value("hello world") == "hello world"
    assert coerce_config_value("some_string") == "some_string"


def test_unwrap_toml_value():
    class MockTomlVal:
        def unwrap(self):
            return {"inner": 123}

    assert unwrap_toml_value(MockTomlVal()) == {"inner": 123}
    assert unwrap_toml_value("plain_val") == "plain_val"
    assert unwrap_toml_value(42) == 42


def test_cli_config_init_and_env(tmp_path, monkeypatch):
    # With explicit config_dir
    cfg = CLIConfig(config_dir=tmp_path)
    assert cfg.config_dir == tmp_path
    assert cfg.filename == "cli.toml"

    # With SPRITZLE_CONFIG env var
    env_dir = tmp_path / "env_config"
    monkeypatch.setenv("SPRITZLE_CONFIG", str(env_dir))
    cfg_env = CLIConfig()
    assert cfg_env.config_dir == env_dir

    # With SPRITZLE_CONFIG_DIR env var
    monkeypatch.delenv("SPRITZLE_CONFIG")
    env_dir2 = tmp_path / "env_config_dir"
    monkeypatch.setenv("SPRITZLE_CONFIG_DIR", str(env_dir2))
    cfg_env2 = CLIConfig()
    assert cfg_env2.config_dir == env_dir2

    # Without env vars, uses home
    monkeypatch.delenv("SPRITZLE_CONFIG_DIR")
    with patch("spritzle.cli.config.Path.home", return_value=tmp_path):
        cfg_home = CLIConfig()
        assert cfg_home.config_dir == tmp_path / ".config" / "spritzle"


def test_cli_config_crud_and_mapping(tmp_path):
    cfg = CLIConfig(config_dir=tmp_path, defaults={"theme": "modern", "plain": False})

    # Default lookup
    assert cfg["theme"] == "modern"
    assert cfg["plain"] is False
    assert "theme" in cfg
    assert "plain" in cfg
    assert "unknown" not in cfg
    with pytest.raises(KeyError):
        _ = cfg["unknown"]

    # Set and modify
    assert not cfg.is_modified("theme")
    cfg["theme"] = "dark"
    assert cfg.is_modified("theme")
    assert cfg["theme"] == "dark"

    # Reload from disk
    cfg_reload = CLIConfig(config_dir=tmp_path, defaults={"theme": "modern", "plain": False})
    assert cfg_reload["theme"] == "dark"

    # Iteration and len
    keys = list(cfg)
    assert "theme" in keys
    assert "plain" in keys
    assert len(cfg) >= 2

    # as_dict
    d = cfg.as_dict()
    assert d["theme"] == "dark"
    assert d["plain"] is False

    # Unset
    assert cfg.unset("theme") is True
    assert not cfg.is_modified("theme")
    assert cfg["theme"] == "modern"
    assert cfg.unset("nonexistent") is False

    # Delitem
    cfg["custom"] = 999
    assert cfg["custom"] == 999
    del cfg["custom"]
    assert "custom" not in cfg
    with pytest.raises(KeyError):
        del cfg["custom"]

    # Reset
    cfg["theme"] = "solarized"
    cfg["color"] = True
    assert cfg.config_file.exists()
    cfg.reset()
    assert not cfg.config_file.exists()
    assert cfg["theme"] == "modern"


def test_cli_config_corrupted_file_backup(tmp_path):
    config_file = tmp_path / "cli.toml"
    config_file.write_text("corrupted [[[ toml syntax", encoding="utf-8")

    cfg = CLIConfig(config_dir=tmp_path)
    assert cfg._unparseable is True

    # Saving when unparseable creates .bak
    cfg["plain"] = True

    bak_file = tmp_path / "cli.toml.bak"
    assert bak_file.exists()
    assert bak_file.read_text(encoding="utf-8") == "corrupted [[[ toml syntax"
    assert cfg._unparseable is False
    assert cfg["plain"] is True


def test_cli_config_reset_handles_oserror(tmp_path):
    cfg = CLIConfig(config_dir=tmp_path)
    cfg["plain"] = True
    assert cfg.config_file.exists()

    with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
        cfg.reset()
    assert cfg["plain"] is False


def test_remotes_config_init_and_env(tmp_path, monkeypatch):
    cfg = RemotesConfig(config_dir=tmp_path)
    assert cfg.config_dir == tmp_path
    assert cfg.filename == "remotes.toml"

    env_dir = tmp_path / "env_remotes"
    monkeypatch.setenv("SPRITZLE_CONFIG", str(env_dir))
    cfg_env = RemotesConfig()
    assert cfg_env.config_dir == env_dir

    monkeypatch.delenv("SPRITZLE_CONFIG")
    with patch("spritzle.cli.config.Path.home", return_value=tmp_path):
        cfg_home = RemotesConfig()
        assert cfg_home.config_dir == tmp_path / ".config" / "spritzle"


def test_remotes_config_crud(tmp_path):
    cfg = RemotesConfig(config_dir=tmp_path)
    assert cfg.get_remotes() == {}
    assert cfg.get_remote("seedbox") is None
    assert cfg.get_default_remote() is None

    # Set remote
    cfg.set_remote(
        name="seedbox",
        url="http://192.168.1.10:8080",
        daemon_id="spz_d_test1",
        key="spritzle_key1",
        insecure=True,
        ca_cert="/path/to/ca.pem",
        fingerprint="AA:BB:CC",
    )
    cfg.set_default_remote("seedbox")

    remote = cfg.get_remote("seedbox")
    assert remote is not None
    assert remote["url"] == "http://192.168.1.10:8080"
    assert remote["daemon_id"] == "spz_d_test1"
    assert remote["key"] == "spritzle_key1"
    assert remote["insecure"] is True
    assert remote["ca_cert"] == "/path/to/ca.pem"
    assert remote["fingerprint"] == "AA:BB:CC"
    assert cfg.get_default_remote() == "seedbox"

    # Reload from disk
    cfg_loaded = RemotesConfig(config_dir=tmp_path)
    assert "seedbox" in cfg_loaded.get_remotes()
    assert cfg_loaded.get_default_remote() == "seedbox"

    # Add second remote
    cfg.set_remote(
        name="vps",
        url="http://vps.example.com:8080",
        daemon_id="spz_d_test2",
        key="spritzle_key2",
    )
    remotes = cfg.get_remotes()
    assert len(remotes) == 2
    assert "seedbox" in remotes
    assert "vps" in remotes

    # Remove non-default remote
    assert cfg.remove_remote("vps") is True
    assert cfg.get_remote("vps") is None
    assert cfg.get_default_remote() == "seedbox"

    # Remove default remote clears default_remote
    assert cfg.remove_remote("seedbox") is True
    assert cfg.get_remote("seedbox") is None
    assert cfg.get_default_remote() is None
    assert cfg.remove_remote("nonexistent") is False


def test_remotes_config_corrupted_file_backup(tmp_path):
    config_file = tmp_path / "remotes.toml"
    config_file.write_text("bad [[[ toml", encoding="utf-8")

    cfg = RemotesConfig(config_dir=tmp_path)
    assert cfg._unparseable is True

    cfg.set_remote("box", "http://127.0.0.1:8080", "spz_d_1", "spritzle_k")

    bak_file = tmp_path / "remotes.toml.bak"
    assert bak_file.exists()
    assert bak_file.read_text(encoding="utf-8") == "bad [[[ toml"
    assert cfg._unparseable is False
    assert cfg.get_remote("box") is not None


def test_remotes_config_ensure_local_remote(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    local_file = state_dir / "local_remote.json"

    cfg = RemotesConfig(config_dir=tmp_path)
    # When file does not exist
    assert cfg.ensure_local_remote(state_dir=state_dir) is None

    # Write valid local_remote.json
    local_data = {
        "url": "http://127.0.0.1:54321",
        "daemon_id": "spz_d_local_123",
        "api_key": "spritzle_local_key",
    }
    local_file.write_text(json.dumps(local_data), encoding="utf-8")

    # Call ensure_local_remote
    remote = cfg.ensure_local_remote(state_dir=state_dir)
    assert remote is not None
    assert remote["url"] == "http://127.0.0.1:54321"
    assert remote["daemon_id"] == "spz_d_local_123"
    assert remote["key"] == "spritzle_local_key"
    assert cfg.get_default_remote() == "local"

    # Calling again when nothing changed is a no-op
    remote2 = cfg.ensure_local_remote(state_dir=state_dir)
    assert remote2 == remote

    # With SPRITZLE_STATE_DIR environment variable
    monkeypatch.setenv("SPRITZLE_STATE_DIR", str(state_dir))
    remote_env = cfg.ensure_local_remote()
    assert remote_env == remote

    # Malformed local_remote.json doesn't crash
    local_file.write_text("invalid json", encoding="utf-8")
    assert cfg.ensure_local_remote(state_dir=state_dir) is not None


def test_cli_config_backup_and_chmod_oserror(tmp_path):
    config_file = tmp_path / "cli.toml"
    config_file.write_text("bad [[[ toml", encoding="utf-8")
    cfg = CLIConfig(config_dir=tmp_path)
    assert cfg._unparseable is True

    # Test shutil.copy2 error and os.chmod error
    with patch("shutil.copy2", side_effect=OSError("Disk full")), patch("os.chmod", side_effect=OSError("Not permitted")):
        cfg["plain"] = True
    assert cfg["plain"] is True


def test_remotes_config_edge_cases(tmp_path):
    # Non-dict remotes in doc
    cfg = RemotesConfig(config_dir=tmp_path)
    cfg._doc["remotes"] = "not_a_dict"
    assert cfg.get_remotes() == {}

    # Corrupted file with copy2 OSError and chmod OSError
    config_file = tmp_path / "remotes.toml"
    config_file.write_text("bad [[[ toml", encoding="utf-8")
    cfg_bad = RemotesConfig(config_dir=tmp_path)
    assert cfg_bad._unparseable is True

    with patch("shutil.copy2", side_effect=OSError("Disk full")), patch("os.chmod", side_effect=OSError("Not permitted")):
        cfg_bad.set_remote("box", "http://127.0.0.1:8080", "spz_d_1", "key")
    assert cfg_bad.get_remote("box") is not None
