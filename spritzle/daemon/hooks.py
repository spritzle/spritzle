#
# spritzle/hooks.py
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
from pathlib import Path
import os
import logging
import subprocess

log = logging.getLogger("spritzle")


class Hooks:
    def __init__(self, path):
        self.path = Path(path)
        self._tasks = set()

    def find_hooks(self, hook):
        hooks = []
        if self.path.exists():
            for p in self.path.iterdir():
                if not p.is_file():
                    continue
                if not p.name[0].isalnum():
                    continue
                if p.name.endswith(hook):
                    if not os.access(p, os.X_OK):
                        log.warning(
                            f"Hook file '{p}' matches hook '{hook}' but is not executable. Run 'chmod +x {p}'."
                        )
                        continue
                    hooks.append(p.resolve())

        return sorted(hooks)

    async def run_hook(self, hook, *args):
        log.info(f"run_hook start hook={hook} args={args}")
        try:
            p = await asyncio.create_subprocess_exec(
                hook,
                *args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await p.communicate()
            if p.returncode != 0:
                log.error(
                    (
                        f"run_hook fail retcode={p.returncode} cmd={hook} "
                        f"output={stderr or stdout}"
                    )
                )
            else:
                log.info(f"run_hook success args={args}")
        except Exception as e:
            log.error(f"run_hook exception: {e}")

    def run_hooks(self, hook_name, *args):
        loop = asyncio.get_running_loop()
        for hook in self.find_hooks(hook_name):
            task = loop.create_task(self.run_hook(hook, *args))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
