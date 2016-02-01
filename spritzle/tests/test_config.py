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

from spritzle.config import Config

import tempfile
import os
import shutil


def test_config_init_no_dir():
    tmpdir = os.path.join(tempfile.gettempdir(), 'spritzletmpdir')
    home = os.environ['HOME']
    os.environ['HOME'] = tmpdir

    c = Config()

    os.environ['HOME'] = home

    assert c.file == os.path.join(
        tmpdir, '.config', 'spritzle', 'spritzle.conf')

    assert os.path.isfile(
        os.path.join(
            tmpdir, '.config', 'spritzle', 'spritzle.conf'))

    shutil.rmtree(tmpdir)


def test_config_init_with_dir():
    with tempfile.TemporaryDirectory() as tempdir:
        Config(config_dir=tempdir)


def test_config_save():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c.save()
        old = c.config
        c.load()
        assert old == c.config


def test_config_load():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c['foo'] = 1
        old = c.config
        c.load()
        assert c.config == old


def test_contains():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c['foo'] = 1
        assert 'foo' in c
        assert c['foo'] == 1


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
