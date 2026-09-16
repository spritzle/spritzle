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

import asyncio
import fcntl
from pathlib import Path
import secrets
import sys
import traceback
from typing import Optional

import aiohttp.web
import click

from .resource.auth import routes as auth_routes
from .resource.auth import auth_middleware, create_jwt_token
from .resource.config import routes as config_routes
from .resource.core import routes as core_routes
from .resource.session import routes as session_routes
from .resource.torrent import routes as torrent_routes

from .keys import APP_KEY_CONFIG, APP_KEY_CORE, APP_KEY_LOG
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
        try:
            body = await request.text()
        except UnicodeDecodeError:
            body = "<non-utf8 binary data>"
    log = request.app[APP_KEY_LOG]
    log.debug("*" * 20 + "REQUEST" + "*" * 20)
    log.debug(f"URL: {request.rel_url}")
    log.debug(f"METHOD: {request.method}")
    safe_headers = {
        k: ("***REDACTED***" if k.lower() == "authorization" else v)
        for k, v in request.headers.items()
    }
    log.debug(f"HEADERS: {safe_headers}")
    if request.rel_url.path == "/auth":
        log.debug("BODY: ***REDACTED (auth)***")
    else:
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
        log = request.app.get(APP_KEY_LOG)
        if log:
            log.error(
                f"Unhandled exception in {request.method} {request.rel_url}:\n{tb}"
            )
        response = aiohttp.web.Response(
            status=500,
            reason="Internal Server Error",
            text="An internal error occurred in Spritzle.",
        )
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

    app[APP_KEY_LOG] = log
    app[APP_KEY_CORE] = core
    app[APP_KEY_CONFIG] = config

    app.middlewares.extend([error_middleware, debug_middleware])

    async def on_startup(app):
        await app[APP_KEY_CORE].start()

    async def on_shutdown(app):
        log.info("Shutdown sequence initiated..")
        try:
            await app[APP_KEY_CORE].stop()
        except Exception:
            # We don't want to stop the shutdown sequence if something fails
            log.error(f"Error during shutdown: {traceback.format_exc()}")
        log.info("Shutdown sequence completed.")

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    app.router.add_routes(auth_routes)
    app.router.add_routes(config_routes)
    app.router.add_routes(core_routes)
    app.router.add_routes(session_routes)
    app.router.add_routes(torrent_routes)


def run_daemon(
    host: str = "127.0.0.1",
    port: int = 8080,
    debug: bool = False,
    config_dir: Optional[str] = None,
    log_level: str = "INFO",
):
    log = setup_logger(name="spritzle", level=log_level)
    log.info(
        f"spritzled starting.. host={host}, port={port}, config_dir={config_dir}, log_level={log_level}, debug={debug}"
    )

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.set_debug(debug)

    config = Config(config_dir=config_dir)

    # Prevent more than one process using the same config path from running.
    f = Path(config.path, "spritzled.lock").open(mode="w")
    try:
        fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError as e:
        log.error(f"Another instance of Spritzle is running: {e}")
        log.error("Exiting..")
        sys.exit(1)

    setup_app(app, Core(config), log)
    # Auth middleware is outside setup_app because we don't want it for unit tests
    app.middlewares.append(auth_middleware)
    try:
        aiohttp.web.run_app(app, host=host, port=port, loop=loop)
    except OSError as e:
        log.error(f"Failed to bind to {host}:{port}: {e}")
        log.error(f"Specify another port with -p / --port (e.g. spritzled -p {port + 1}).")
        sys.exit(1)


@click.group(invoke_without_command=True)
@click.option(
    "-H",
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host to listen on.",
)
@click.option("--debug", default=False, is_flag=True, help="Enable debug mode.")
@click.option("-p", "--port", default=8080, type=int, show_default=True, help="Port to listen on.")
@click.option(
    "-c",
    "--config-dir",
    "--config_dir",
    "config_dir",
    default=None,
    type=str,
    help="Configuration directory.",
)
@click.option(
    "-l",
    "--log-level",
    default="INFO",
    show_default=True,
    help="Log level.",
)
@click.pass_context
def main(ctx, host, port, debug, config_dir, log_level):
    """Spritzle daemon."""
    if ctx.invoked_subcommand is None:
        run_daemon(
            host=host,
            port=port,
            debug=debug,
            config_dir=config_dir,
            log_level=log_level,
        )


@main.command("token", short_help="Generate an authentication token.")
@click.option(
    "-c",
    "--config-dir",
    "--config_dir",
    "config_dir",
    default=None,
    type=str,
    help="Configuration directory.",
)
@click.option(
    "-e",
    "--expires-in",
    default=None,
    type=float,
    help="Token expiration time in seconds (0 for no expiration).",
)
@click.pass_context
def generate_token(ctx, config_dir, expires_in):
    """Generate an authentication JWT token for the daemon."""
    cfg_dir = config_dir or (ctx.parent.params.get("config_dir") if ctx.parent else None)
    config = Config(config_dir=cfg_dir)
    if not config["auth_secret"]:
        config["auth_secret"] = secrets.token_hex()

    if expires_in is not None:
        timeout_val = float(expires_in)
    else:
        try:
            timeout_val = float(config.get("auth_timeout", 120))
        except (TypeError, ValueError):
            timeout_val = 120.0

    token = create_jwt_token(config["auth_secret"], timeout_val)
    click.echo(token)


