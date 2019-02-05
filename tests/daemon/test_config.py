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
    tmpdir = Path(tempfile.gettempdir(), 'spritzletmpdir')
    with patch('pathlib.Path.home', return_value=tmpdir):
        c = Config()

    assert c.config_file == Path(
        tmpdir, '.config', 'spritzle', 'spritzled.conf')

    assert c.config_file.is_file()

    shutil.rmtree(tmpdir)


def test_config_init_with_dir():
    with tempfile.TemporaryDirectory() as tempdir:
        Config(config_dir=tempdir)


def test_config_save():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c['foo'] = 1
        c.save()
        old = c.data
        c.load()
        assert old == c.data

    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir, in_memory=True)
        c['foo'] = 1
        c.save()
        assert not Path(tempdir, 'spritzle.conf').exists()


def test_config_load():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c.load()
        assert c.data == {}
        c['foo'] = 1
        old = c.data
        c.load()
        assert c.data == old

        c = Config(config_dir=tempdir, in_memory=True)
        c.load()
        assert c.data == {}


def test_len():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        assert len(c) == 0
        c['foo'] = 1
        assert len(c) == 1
        c['bar'] = 1
        assert len(c) == 2


def test_iter():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c['foo'] = 1
        assert next(iter(c)) == 'foo'


def test_delitem():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c['foo'] = 1
        del c['foo']
        assert 'foo' not in c


def test_get():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        assert c.get('foo') is None
        assert c.get('foo', 1) == 1
        c['foo'] = 2
        assert c.get('foo') == 2


def test_initial():
    c = Config(in_memory=True, initial={'foo': 1})
    assert c.get('foo') == 1


def test_defaults():
    c = Config(in_memory=True, defaults={'foo': 1})
    assert c.get('foo') == 1
    c['foo'] = 2
    assert c.get('foo') == 2
    del c['foo']
    assert c.get('foo') == 1


def test_init_load():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c['foo'] = 1
        c.save()
        c = Config(config_dir=tempdir)
        assert c.get('foo') == 1
