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
        if request.content_type in ('application/x-www-form-urlencoded',
                                    'multipart/form-data'):
            body = await request.post()
        else:
            body = await request.text()
        log = app['spritzle.log']
        log.debug('*'*20 + 'REQUEST' + '*'*20)
        log.debug(f'URL: {request.rel_url}')
        log.debug(f'METHOD: {request.method}')
        log.debug(f'HEADERS: {request.headers}')
        log.debug(f'BODY: {body}')
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
    app.router.add_route('GET', '/settings',
                         spritzle.resource.settings.get_settings)
    app.router.add_route('PUT', '/settings',
                         spritzle.resource.settings.put_settings)
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

    loop = asyncio.get_event_loop()
    loop.set_debug(args.debug)

    app['spritzle.config'] = Config('spritzle.conf', args.config_dir)
    app['spritzle.core'] = Core(app['spritzle.config'])

    async def on_startup(app):
        await app['spritzle.core'].start()

    async def on_shutdown(app):
        await app['spritzle.core'].stop()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    setup_routes()
    aiohttp.web.run_app(app)
