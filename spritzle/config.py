#
# spritzle/config.py
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

import os
import yaml
import collections.abc


class Config(collections.abc.MutableMapping):
    def __init__(self, filename='spritzle.conf', config_dir=None):
        self.data = {}

        if config_dir is None:
            self.dir = os.path.join(
                os.path.expanduser('~'),
                '.config',
                'spritzle'
            )
        else:
            self.dir = config_dir

        self.file = os.path.join(self.dir, filename)

        if not os.path.isdir(self.dir):
            os.makedirs(self.dir)

        if os.path.isfile(self.file):
            self.load()
        else:
            self.save()

    def load(self):
        if os.path.isfile(self.file):
            self.data = yaml.load(open(self.file, 'r'))

    def save(self):
        yaml.dump(self.data, open(self.file, 'w'))

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def __getitem__(self, key):
        return self.data[key]

    def __delitem__(self, key):
        del self.data[key]
        self.save()
