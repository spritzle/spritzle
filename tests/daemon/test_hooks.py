#
# test_hooks.py
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
from pathlib import Path

from spritzle.daemon.hooks import Hooks


def test_find_hooks():
    with tempfile.TemporaryDirectory() as tmpdir:
        h = Hooks(tmpdir)
        hooks = h.find_hooks("foobar")
        assert len(hooks) == 0

        Path(tmpdir, "_foobar").touch()
        hooks = h.find_hooks("foobar")
        assert len(hooks) == 0
        Path(tmpdir, "_foobar").unlink()

        Path(tmpdir, "foobar", exist_ok=True).mkdir()
        hooks = h.find_hooks("foobar")
        assert len(hooks) == 0
        Path(tmpdir, "foobar").rmdir()

        Path(tmpdir, "foobar").touch()
        hooks = h.find_hooks("foobar")
        assert len(hooks) == 0
        Path(tmpdir, "foobar").unlink()

        Path(tmpdir, "100_foobar").touch(mode=0o777)
        Path(tmpdir, "foobar").touch(mode=0o777)
        hooks = h.find_hooks("foobar")
        assert len(hooks) == 2
        assert hooks[0] == Path(tmpdir, "100_foobar")


async def test_run_hook_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir, "foobar")
        p.write_bytes(b"#!/bin/sh\nexit 0")
        p.chmod(0o777)
        h = Hooks(tmpdir)
        await h.run_hook(p)


async def test_run_hook_fail():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir, "foobar")
        p.write_bytes(b"#!/bin/sh\nexit 1")
        p.chmod(0o777)
        h = Hooks(tmpdir)
        await h.run_hook(p)
