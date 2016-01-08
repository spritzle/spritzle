#
# spritzle/core.py
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

import libtorrent as lt
import pkg_resources

from spritzle.config import Config
from spritzle.alert import Alert

class Core(object):
    def __init__(self):
        pass

    def init(self, config_dir):
        self.config = Config('spritzle.conf', config_dir)

        version = pkg_resources.require("spritzle")[0].version
        version = [int(value.split("-")[0]) for value in version.split(".")]

        while len(version) < 4:
            version.append(0)

        self.session = lt.session(lt.fingerprint("SZ", *version), flags=1)

        self.alert = Alert(self.session)

core = Core()