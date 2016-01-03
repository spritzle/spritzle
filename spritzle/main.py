#
# spritzle/main.py
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
import os
import asyncio

import spritzle.resource.auth
import spritzle.resource.config
import spritzle.resource.session
import spritzle.resource.settings
import spritzle.resource.torrent
import spritzle.resource.user

from spritzle.aiohttp import AiohttpServer
from spritzle.core import core
from spritzle import hooks
from spritzle.error import InvalidEncodingError
from spritzle.hooks import register_default

app = bottle.app()

class Main(object):

    def __init__(self, port, debug=False, reloader=False, config_dir=None):
        self.port = port
        self.debug = debug
        self.reloader = reloader
        self.config_dir = config_dir

    def start(self):
        bootstrap(config_dir=self.config_dir)

        bottle.run(server=AiohttpServer, reloader=self.reloader, port=self.port, debug=self.debug)

def bootstrap(config_dir=None):
    core.init(config_dir)

def main():
    parser = argparse.ArgumentParser(description='Spritzled')
    parser.add_argument('--debug', dest='debug', default=False, action='store_true')
    parser.add_argument('--reload', dest='reload', default=False, action='store_true')
    parser.add_argument('-p', '--port', dest='port', default=8080, type=int)
    parser.add_argument('-c', '--config_dir', dest='config_dir', type=str)

    args = parser.parse_args()

    main = Main(args.port, args.debug, args.reload)
    main.start()
