#
# test_config.py
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

import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from spritzle.daemon.config import Config


def test_config_init_no_dir():
    tmpdir = Path(tempfile.gettempdir(), "spritzletmpdir")
    with patch("pathlib.Path.home", return_value=tmpdir):
        c = Config()

    assert c.config_file == Path(tmpdir, ".config", "spritzle", "daemon.toml")

    assert c.config_file is not None
    assert c.config_file.is_file()

    shutil.rmtree(tmpdir)


def test_config_init_with_dir():
    with tempfile.TemporaryDirectory() as tempdir:
        Config(config_dir=tempdir)


def test_len():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir, defaults={})
        assert len(c) == 0
        c["foo"] = 1
        assert len(c) == 1
        c["bar"] = 1
        assert len(c) == 2


def test_iter():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir, defaults={})
        c["foo"] = 1
        assert next(iter(c)) == "foo"


def test_delitem():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c["foo"] = 1
        del c["foo"]
        assert "foo" not in c


def test_get():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        assert c.get("foo") is None
        assert c.get("foo", 1) == 1
        c["foo"] = 2
        assert c.get("foo") == 2


def test_defaults():
    c = Config(in_memory=True, defaults={"foo": 1})
    assert c.get("foo") == 1
    c["foo"] = 2
    assert c.get("foo") == 2
    del c["foo"]
    assert c.get("foo") == 1


def test_init_load():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c["foo"] = 1
        c = Config(config_dir=tempdir)
        assert c.get("foo") == 1


def test_reset():
    c = Config(in_memory=True)
    c["foo"] = 1
    assert c["foo"] == 1
    c.reset()
    assert c.get("foo") is None


def test_dotted_keys():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir, defaults={"a.b.c": "default_val"})
        assert c["a.b.c"] == "default_val"
        c["a.b.c"] = "new_val"
        assert c["a.b.c"] == "new_val"

        # Verify file on disk has TOML table format
        assert c.config_file is not None
        raw = c.config_file.read_text(encoding="utf-8")
        assert "[a.b]" in raw
        assert 'c = "new_val"' in raw

        # Reloading preserves dotted structure
        c2 = Config(config_dir=tempdir, defaults={"a.b.c": "default_val"})
        assert c2["a.b.c"] == "new_val"

        # Deletion resets to default
        del c2["a.b.c"]
        assert c2["a.b.c"] == "default_val"


def test_file_permissions():
    import stat

    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c["auth_secret"] = "mysecret"
        assert c.config_file is not None
        mode = stat.S_IMODE(c.config_file.stat().st_mode)
        assert mode == 0o600


def test_unwrap_types():
    c = Config(in_memory=True)
    c["my_list"] = ["a", "b", "c"]
    c["my_int"] = 42
    c["my_bool"] = True
    c["my_dict"] = {"nested": "value"}

    assert isinstance(c["my_list"], list)
    assert isinstance(c["my_int"], int)
    assert isinstance(c["my_bool"], bool)
    assert isinstance(c["my_dict"], dict)


def test_as_dict():
    c = Config(in_memory=True, defaults={"def_key": "val1"})
    c["custom_key"] = "val2"
    d = c.as_dict()
    assert d["def_key"] == "val1"
    assert d["custom_key"] == "val2"


def test_delitem_nonexistent():
    import pytest

    c = Config(in_memory=True)
    with pytest.raises(KeyError):
        del c["nonexistent"]


def test_listen_interfaces_config(monkeypatch):
    c = Config(in_memory=True)
    assert c.get("listen_interfaces") == ""

    c["listen_interfaces"] = "tun0:6881"
    assert c.get("listen_interfaces") == "tun0:6881"

    monkeypatch.setenv("SPRITZLE_LISTEN_INTERFACES", "wg0:6881")
    from spritzle.daemon.config import DEFAULTS
    assert "listen_interfaces" in DEFAULTS


def test_state_dir_config(monkeypatch):
    c = Config(in_memory=True)
    assert "state_dir" in c.defaults

    c["state_dir"] = "/tmp/my-custom-state"
    assert c.get("state_dir") == "/tmp/my-custom-state"

    monkeypatch.setenv("SPRITZLE_STATE_DIR", "/tmp/env-state")
    from spritzle.daemon.config import DEFAULTS
    assert "state_dir" in DEFAULTS

