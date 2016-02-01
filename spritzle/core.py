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
        self.alert = Alert()

    def init(self, config_dir):
        self.config = Config('spritzle.conf', config_dir)

        self.session = lt.session({
            'alert_mask': lt.alert.category_t.all_categories,
            'user_agent': 'Spritzle/%s libtorrent/%s' % (
                pkg_resources.require("spritzle")[0].version,
                lt.__version__),
            })

        self.alert.start(self.session)

    def stop(self):
        self.alert.stop()

core = Core()
