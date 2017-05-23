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

DEFAULTS = {
    'auth_password': 'password',
    'auth_secret': 'secret',
    'auth_timeout': 120,
    'auth_allow_hosts': ['127.0.0.1'],
}


class Config(collections.abc.MutableMapping):
    def __init__(self, filename='spritzle.conf', config_dir=None,
                 defaults=None, in_memory=False):

        self.in_memory = in_memory
        self.defaults = defaults or DEFAULTS
        self.data = {}

        if not self.in_memory:
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
        if self.in_memory:
            return

        if os.path.isfile(self.file):
            self.data = yaml.safe_load(open(self.file, 'r')) or {}

    def save(self):
        if self.in_memory:
            return

        f = open(self.file, 'w')
        f.write(
            '''#
# Configuration file for Spritzle. The format is YAML.
#
# Default values:
#
''')
        for key, value in sorted(self.defaults.items()):
            f.write(f'# {key}: {value}\n')

        f.write('#\n# Overrides should be made below this line\n\n')
        if self.data:
            for k, v in sorted(self.data.items()):
                yaml.safe_dump({k: v}, f, default_flow_style=False)

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def __getitem__(self, key):
        if key in self.defaults:
            return self.data.get(key, self.defaults[key])
        return self.data[key]

    def __delitem__(self, key):
        del self.data[key]
        self.save()
