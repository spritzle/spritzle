#
# test_db.py
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

import tempfile
from pathlib import Path

from spritzle.daemon.db import DB


def test_db_init():
    with tempfile.TemporaryDirectory() as tempdir:
        path = Path(tempdir, "tmp.db")

        DB(path=path)

        assert path.exists()
        assert path.is_file()


def test_len():
    db = DB(in_memory=True)
    assert len(db) == 0
    db["foo"] = 1
    assert len(db) == 1
    db["bar"] = 1
    assert len(db) == 2


def test_iter():
    db = DB(in_memory=True)
    db["foo"] = 1
    db["bar"] = 2
    db["baz"] = 3
    # Multiple complete iterations
    assert sorted(list(db)) == ["bar", "baz", "foo"]
    assert sorted(list(db)) == ["bar", "baz", "foo"]

    # Early break followed by full iteration
    for k in db:
        if k == "bar":
            break
    assert sorted(list(db)) == ["bar", "baz", "foo"]

    # Nested iteration
    pairs = []
    for k1 in db:
        for k2 in db:
            pairs.append((k1, k2))
    assert len(pairs) == 9



def test_delitem():
    db = DB(in_memory=True)
    db["foo"] = 1
    del db["foo"]
    assert "foo" not in db


def test_delitem_nonexistent():
    import pytest
    db = DB(in_memory=True)
    with pytest.raises(KeyError):
        del db["nonexistent_key"]



def test_get():
    db = DB(in_memory=True)
    assert db.get("foo") is None
    assert db.get("foo", 1) == 1
    db["foo"] = 2
    assert db.get("foo") == 2


def test_defaults():
    db = DB(in_memory=True, defaults={"foo": 1})
    assert db.get("foo") == 1
    db["foo"] = 2
    assert db.get("foo") == 2
    del db["foo"]
    assert db.get("foo") == 1


def test_init_load():
    with tempfile.TemporaryDirectory() as tempdir:
        path = Path(tempdir, "tmp.db")
        db = DB(path=path)
        db["foo"] = 1
        db = DB(path=path)
        assert db.get("foo") == 1


def test_reset():
    db = DB(in_memory=True)
    db["foo"] = 1
    assert db["foo"] == 1
    db.reset()
    assert db.get("foo") is None


def test_setitem_not_json_serializable():
    import pytest
    db = DB(in_memory=True)
    with pytest.raises(ValueError, match="not JSON serializable"):
        db["foo"] = object()

