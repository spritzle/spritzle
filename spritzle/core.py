#
# spritzle/core.py
#
# Copyright (C) 2011 Andrew Resch <andrewresch@gmail.com>
#               2011 Damien Churchill <damoxc@gmail.com>
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

import json
import bottle
import argparse
import libtorrent

from spritzle import hooks, user

class Core(object):

    def __init__(self, port, debug=False):
        self.port = port
        self.debug = debug

    def start(self):
        hooks.register_default('decode_data', hook_decode_data)
        hooks.register_default('encode_data', hook_encode_data)

        bottle.debug(True)
        bottle.run(reloader=True, port=args.port)

def hook_decode_data(fmt, data):
    if fmt != 'json':
        return None
    try:
        return json.loads(data)
    except TypeError:
        return json.load(data)

def hook_encode_data(fmt, data):
    if fmt != 'json':
        return None
    return json.dumps(data)

def bootstrap():
    hooks.register_default('decode_data', hook_decode_data)
    hooks.register_default('encode_data', hook_encode_data)

def main():
    parser = argparse.ArgumentParser(description='Spritzled')
    parser.add_argument('--debug', dest='debug', default=False, type=bool)
    parser.add_argument('-p', '--port', dest='port', default=8080, type=int)

    args = parser.parse_args()

    core = Core(args.port, args.debug)
    core.start()
