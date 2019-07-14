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
import fcntl
from pathlib import Path
import secrets
import sys
import traceback

import aiohttp.web

from .resource.auth import routes as auth_routes
from .resource.auth import auth_middleware
from .resource.config import routes as config_routes
from .resource.core import routes as core_routes
from .resource.session import routes as session_routes
from .resource.torrent import routes as torrent_routes

from .core import Core
from .config import Config
from .logger import setup_logger


@aiohttp.web.middleware
async def debug_middleware(request, handler):
    if request.content_type in (
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ):
        body = await request.post()
    else:
        body = await request.text()
    log = request.app["spritzle.log"]
    log.debug("*" * 20 + "REQUEST" + "*" * 20)
    log.debug(f"URL: {request.rel_url}")
    log.debug(f"METHOD: {request.method}")
    log.debug(f"HEADERS: {request.headers}")
    log.debug(f"BODY: {body}")
    log.debug("*" * 47)
    return await handler(request)


@aiohttp.web.middleware
async def error_middleware(request, handler):
    try:
        response = await handler(request)
    except aiohttp.web.HTTPException as ex:
        response = ex
    except Exception:
        # Unhandled exception, this is a bug in Spritzle
        tb = "".join(traceback.format_exception(*sys.exc_info()))
        response = aiohttp.web.Response(status=500, reason="Spritzle Bug", text=tb)
    if response.status < 400:
        return response
    return aiohttp.web.json_response(
        {
            "status": response.status,
            "reason": response.reason,
            "message": response.text,
        },
        status=response.status,
        reason=response.reason,
    )


app = aiohttp.web.Application()


def setup_app(app, core, log):
    config = core.config
    if not config["auth_secret"]:
        config["auth_secret"] = secrets.token_hex()

    app["spritzle.log"] = log
    app["spritzle.core"] = core
    app["spritzle.config"] = config

    app.middlewares.extend([error_middleware, debug_middleware])

    async def on_startup(app):
        await app["spritzle.core"].start()

    async def on_shutdown(app):
        await app["spritzle.core"].stop()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    app.router.add_routes(auth_routes)
    app.router.add_routes(config_routes)
    app.router.add_routes(core_routes)
    app.router.add_routes(session_routes)
    app.router.add_routes(torrent_routes)


def main():
    parser = argparse.ArgumentParser(description="Spritzled")
    parser.add_argument("--debug", dest="debug", default=False, action="store_true")
    parser.add_argument("-p", "--port", dest="port", default=8080, type=int)
    parser.add_argument("-c", "--config_dir", dest="config_dir", type=str)
    parser.add_argument("-l", "--log-level", default="INFO", dest="log_level", type=str)
    args = parser.parse_args()

    log = setup_logger(name="spritzle", level=args.log_level)
    log.info(f"spritzled starting.. args: {args}")

    loop = asyncio.get_event_loop()
    loop.set_debug(args.debug)

    config = Config("spritzle.conf", args.config_dir)

    # Prevent more than one process using the same config path from running.
    f = Path(config.path, "spritzled.lock").open(mode="w")
    try:
        fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError as e:
        log.error(f"Another instance of Spritzle is running: {e}")
        log.error("Exiting..")
        sys.exit(0)

    setup_app(app, Core(config), log)
    # Auth middleware is outside setup_app because we don't want it for unit tests
    app.middlewares.append(auth_middleware)
    aiohttp.web.run_app(app, port=args.port)
