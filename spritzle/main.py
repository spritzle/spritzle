#
# spritzle/main.py
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

import argparse
import asyncio
import signal
import functools
import concurrent

import aiohttp

import spritzle.resource.auth
import spritzle.resource.config
import spritzle.resource.session
import spritzle.resource.settings
import spritzle.resource.torrent

from spritzle.core import Core
from spritzle.config import Config
from spritzle.logger import setup_logger


async def debug_middleware(app, handler):
    async def middleware(request):
        body = await request.text()
        post = await request.post()
        log = app['spritzle.log']
        log.debug('*'*20 + 'REQUEST' + '*'*20)
        log.debug(f'URL: {request.rel_url}')
        log.debug(f'METHOD: {request.method}')
        log.debug(f'HEADERS: {request.headers}')
        log.debug(f'BODY: {body}')
        log.debug(f'POST: {post}')
        log.debug('*'*47)
        return await handler(request)
    return middleware

app = aiohttp.web.Application(
    middlewares=[debug_middleware,
                 spritzle.resource.auth.auth_middleware])


def setup_routes():
    app.router.add_route('POST', '/auth',
                         spritzle.resource.auth.post_auth)
    app.router.add_route('GET', '/config',
                         spritzle.resource.config.get_config)
    app.router.add_route('PUT', '/config',
                         spritzle.resource.config.put_config)
    app.router.add_route('GET', '/session',
                         spritzle.resource.session.get_session)
    app.router.add_route('GET', '/session/dht',
                         spritzle.resource.session.get_session_dht)
    app.router.add_route('GET', '/torrent',
                         spritzle.resource.torrent.get_torrent)
    app.router.add_route('GET', '/torrent/{tid}',
                         spritzle.resource.torrent.get_torrent)
    app.router.add_route('POST', '/torrent',
                         spritzle.resource.torrent.post_torrent)
    app.router.add_route('DELETE', '/torrent',
                         spritzle.resource.torrent.delete_torrent)
    app.router.add_route('DELETE', '/torrent/{tid}',
                         spritzle.resource.torrent.delete_torrent)


class Main(object):

    def __init__(self, port, debug=False, config_dir=None):
        self.port = port
        self.debug = debug
        self.loop = asyncio.get_event_loop()
        self.loop.set_debug(self.debug)

        app['spritzle.config'] = Config('spritzle.conf', config_dir)
        app['spritzle.core'] = Core()

        # Create an executor so that we can call shutdown(wait=True) on it
        # when we shutdown the server.  This is done to allow Tasks to
        # properly finish execution on shutdown.
        self.executor = concurrent.futures.ThreadPoolExecutor(5)
        self.loop.set_default_executor(self.executor)

    def stop(self):
        app['spritzle.core'].stop()
        self.executor.shutdown(wait=True)
        self.loop.stop()

    def start(self):
        setup_routes()

        for s in (signal.SIGINT, signal.SIGTERM):
            self.loop.add_signal_handler(s, functools.partial(self.stop))

        app['spritzle.core'].start()
        aiohttp.web.run_app(app)


def main():
    parser = argparse.ArgumentParser(description='Spritzled')
    parser.add_argument(
        '--debug', dest='debug', default=False, action='store_true')
    parser.add_argument('-p', '--port', dest='port', default=8080, type=int)
    parser.add_argument('-c', '--config_dir', dest='config_dir', type=str)
    parser.add_argument('-l', '--log-level', default='INFO',
                        dest='log_level', type=str)

    args = parser.parse_args()

    log = setup_logger(name='spritzle', level=args.log_level)
    log.info(f'spritzled starting.. args: {args}')
    app['spritzle.log'] = log
    Main(args.port, args.debug, args.config_dir).start()
