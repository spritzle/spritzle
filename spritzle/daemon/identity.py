#
# spritzle/daemon/identity.py
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

from pathlib import Path
import secrets
from typing import Union


class Identity:
    """Manages the persistent identity of a Spritzle daemon instance."""

    def __init__(self, state_dir: Union[Path, str]):
        self.state_dir = Path(state_dir)
        self.identity_file = self.state_dir / "identity"
        self._daemon_id = self._load_or_create_id()

    def _load_or_create_id(self) -> str:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if self.identity_file.exists():
            try:
                content = self.identity_file.read_text().strip()
                if content:
                    return content
            except OSError:
                pass

        new_id = f"spz_d_{secrets.token_hex(8)}"
        self.identity_file.write_text(f"{new_id}\n")
        return new_id

    @property
    def daemon_id(self) -> str:
        return self._daemon_id
