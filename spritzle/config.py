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
import json
import asyncio

class Config(object):
    def __init__(self, filename='spritzle.conf', config_dir=None):
        
        self.config = {}

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
            self.config = json.load(open(self.file, 'r'))

    def save(self):
        json.dump(self.config, open(self.file, 'w'))

    def __contains__(self, item):
        return item in self.config

    def __setitem__(self, key, value):
        self.config[key] = value
        self.save()

    def __getitem__(self, key):
        return self.config[key]

    def __delitem__(self, key):
        del self.config[key]
        self.save()

    def get(self, key, default=None):
        return self.config.get(key, default)
