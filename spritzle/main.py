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

from spritzle.core import core

app = aiohttp.web.Application()


def run_app(app, *, host='0.0.0.0', port=None,
            shutdown_timeout=60.0, ssl_context=None,
            print=print):  # pragma: no cover
    """Run an app locally

    TODO: Remove this when aiohttp release has it.
    """
    if port is None:
        if not ssl_context:
            port = 8080
        else:
            port = 8443

    loop = app.loop

    handler = app.make_handler()
    srv = loop.run_until_complete(loop.create_server(handler, host, port,
                                                     ssl=ssl_context))

    scheme = 'https' if ssl_context else 'http'
    prompt = '127.0.0.1' if host == '0.0.0.0' else host
    print("======== Running on {scheme}://{prompt}:{port}/ ========\n"
          "(Press CTRL+C to quit)".format(
              scheme=scheme, prompt=prompt, port=port))

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no branch
        pass
    finally:
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(handler.finish_connections(shutdown_timeout))
        loop.run_until_complete(app.finish())
    loop.close()


class Main(object):

    def __init__(self, port, debug=False, config_dir=None):
        self.port = port
        self.debug = debug
        self.config_dir = config_dir
        self.loop = asyncio.get_event_loop()
        self.loop.set_debug(self.debug)

        # Create an executor so that we can call shutdown(wait=True) on it
        # when we shutdown the server.  This is done to allow Tasks to
        # properly finish execution on shutdown.
        self.executor = concurrent.futures.ThreadPoolExecutor(5)
        self.loop.set_default_executor(self.executor)

    def setup_routes(self):
        # TODO: Turn these into decorators.
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

    def stop(self):
        core.stop()
        self.executor.shutdown(wait=True)
        self.loop.stop()

    def start(self):
        bootstrap(config_dir=self.config_dir)

        self.setup_routes()

        for s in (signal.SIGINT, signal.SIGTERM):
            self.loop.add_signal_handler(s, functools.partial(self.stop))

        run_app(app)


def bootstrap(config_dir=None):
    core.init(config_dir)


def main():
    parser = argparse.ArgumentParser(description='Spritzled')
    parser.add_argument(
        '--debug', dest='debug', default=False, action='store_true')
    parser.add_argument('-p', '--port', dest='port', default=8080, type=int)
    parser.add_argument('-c', '--config_dir', dest='config_dir', type=str)

    args = parser.parse_args()

    main = Main(args.port, args.debug, args.config_dir)
    main.start()
