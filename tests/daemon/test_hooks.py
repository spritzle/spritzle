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

import asyncio
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

        Path(tmpdir, "foobar").mkdir(exist_ok=True)
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


async def test_hooks_blocking():
    # Verify that run_hook blocks the loop (fails if parallel task doesn't run)
    # or that it doesn't block (passes if parallel task runs).
    # We expect this test to FAIL (prove blocking) completely or show significant delay
    # if implementation is blocking.
    # Actually, proving it blocks in a single threaded test is tricky.
    # If it blocks, `await run_hook` will not yield to other tasks.

    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir, "foobar")
        # Sleep for 0.1 second
        p.write_bytes(b"#!/bin/sh\nsleep 0.1")
        p.chmod(0o777)
        h = Hooks(tmpdir)

        # Create a background task that sets a flag
        flag = False

        async def set_flag():
            nonlocal flag
            await asyncio.sleep(0.01)
            flag = True

        asyncio.create_task(set_flag())

        # Run the hook. If blocking, set_flag won't run until hook is done (1s).
        # We start the hook.
        await h.run_hook(p)

        # If it was non-blocking/async, set_flag should have run during the 1s sleep.
        # If it was blocking, set_flag only runs after run_hook returns.

        # However, run_hook is awaited.
        # If run_hook uses subprocess.run (blocking), it blocks the loop.
        # So 'await h.run_hook(p)' blocks for 1s. 'task' is scheduled but loop is blocked.
        # After 1s, run_hook returns. The loop resumes. 'task' might run now?
        # We check flag immediately.

        # If blocking:
        # 1. create_task(set_flag) -> scheduled
        # 2. run_hook(p) -> blocks loop for 1s.
        # 3. run_hook returns.
        # 4. We check flag. Task hasn't had CPU time yet because loop was blocked?
        #    Or loop executes pending tasks?

        # Actually, let's verify if flag is set.
        # If non-blocking (subprocess_exec):
        # 1. create_task(set_flag)
        # 2. run_hook(p) -> starts process, awaits 'wait()'.
        #    Yields control.
        # 3. Loop runs set_flag(). sleep(0.1) -> yields.
        # 4. set_flag resumes after 0.1s -> sets flag=True.
        # 5. run_hook finishes after 1s.
        # 6. We check flag. It should be True.

        assert flag, "Event loop was blocked by run_hook"


async def test_run_hooks_tracks_tasks():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir, "my_hook")
        p.write_bytes(b"#!/bin/sh\nexit 0")
        p.chmod(0o777)
        h = Hooks(tmpdir)
        h.run_hooks("my_hook")
        assert len(h._tasks) == 1
        # Wait for tasks to complete
        await asyncio.gather(*list(h._tasks))
        assert len(h._tasks) == 0

