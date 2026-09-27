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
import sys

import traceback
from typing import Optional

import aiohttp.web
import click

from .resource.auth import routes as auth_routes
from .resource.auth import auth_middleware
from .resource.config import routes as config_routes
from .resource.core import routes as core_routes
from .resource.log import routes as log_routes
from .resource.session import routes as session_routes
from .resource.torrent import routes as torrent_routes

from .keys import (
    APP_KEY_CONFIG,
    APP_KEY_CORE,
    APP_KEY_IDENTITY,
    APP_KEY_KEY_MANAGER,
    APP_KEY_LOG,
)
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
        k: ("***REDACTED***" if k.lower() in ("authorization", "x-api-key") else v)
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
        if isinstance(response, aiohttp.web.HTTPException):
            raise response
        return response
    headers = {
        k: v
        for k, v in response.headers.items()
        if k.lower() not in ("content-type", "content-length")
    }
    if response.text and not response.text.startswith(f"{response.status}: "):
        safe_msg = response.text.rstrip("\r\n")
    else:
        safe_msg = response.reason or "Error"
    return aiohttp.web.json_response(
        {
            "status": response.status,
            "reason": response.reason,
            "message": safe_msg,
        },
        status=response.status,
        reason=response.reason,
        headers=headers,
    )




def create_app(core, log) -> aiohttp.web.Application:
    new_app = aiohttp.web.Application()
    setup_app(new_app, core, log)
    return new_app


def setup_app(app, core, log):
    config = core.config

    app[APP_KEY_LOG] = log
    app[APP_KEY_CORE] = core
    app[APP_KEY_CONFIG] = config
    app[APP_KEY_IDENTITY] = core.identity
    app[APP_KEY_KEY_MANAGER] = core.key_manager

    from .logger import get_log_buffer_handler

    buffer_handler = get_log_buffer_handler()
    if buffer_handler not in log.handlers:
        log.addHandler(buffer_handler)

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
    app.router.add_routes(log_routes)
    app.router.add_routes(session_routes)
    app.router.add_routes(torrent_routes)


CONTEXT_SETTINGS = dict(auto_envvar_prefix="SPRITZLE")


def check_libtorrent() -> None:
    try:
        import libtorrent  # noqa: F401
    except ModuleNotFoundError:
        click.echo(
            "Error: 'libtorrent' Python bindings are required to run the Spritzle daemon.\n\n"
            "Installation options:\n"
            "  1. Install wheel with daemon dependencies:\n"
            "     pip install 'spritzle[daemon]'\n"
            "     # or with uv:\n"
            "     uv tool install 'spritzle[daemon]'\n\n"
            "  2. Install via your Linux distribution package manager:\n"
            "     Arch Linux: sudo pacman -S python-libtorrent\n"
            "     (Note: Ensure virtual environment is created with --system-site-packages)\n\n"
            "Note: The 'spritzle' CLI is pure-Python and does not require libtorrent.",
            file=sys.stderr,
        )
        sys.exit(1)


def get_existing_event_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Get the current event loop if one is already set and not closed, otherwise None."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        pass

    try:
        import asyncio.events as _events

        if getattr(_events, "_event_loop_policy", None) is None:
            init_fn = getattr(_events, "_init_event_loop_policy", None)
            if callable(init_fn):
                init_fn()
        policy = getattr(_events, "_event_loop_policy", None)
        if policy is not None:
            loop = getattr(getattr(policy, "_local", None), "_loop", None)
            if loop is not None and not loop.is_closed():
                return loop
            return None
    except Exception:
        pass

    return None


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get the current event loop if set, or create and set a new one without DeprecationWarning."""
    existing = get_existing_event_loop()
    if existing is not None:
        return existing

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


def run_daemon(
    host: str = "127.0.0.1",
    port: int = 17382,
    debug: bool = False,
    config_dir: Optional[str] = None,
    state_dir: Optional[str] = None,
    log_level: str = "INFO",
    listen_interfaces: Optional[str] = None,
    logfile: Optional[str] = None,
):
    check_libtorrent()
    config = Config(config_dir=config_dir)
    raw_logfile = logfile or config.get("log_file") or config.get("logfile")
    effective_logfile = (
        str(raw_logfile).strip()
        if isinstance(raw_logfile, (str, Path)) and str(raw_logfile).strip()
        else None
    )
    try:
        max_bytes = int(config.get("log_rotate_max_bytes", 10 * 1024 * 1024))
    except (ValueError, TypeError):
        max_bytes = 10 * 1024 * 1024
    try:
        backup_count = int(config.get("log_rotate_backup_count", 5))
    except (ValueError, TypeError):
        backup_count = 5

    log = setup_logger(
        name="spritzle",
        level=log_level,
        logfile=effective_logfile,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
    log.info(
        f"spritzled starting.. host={host}, port={port}, config_dir={config_dir}, state_dir={state_dir}, log_level={log_level}, logfile={effective_logfile}, debug={debug}, listen_interfaces={listen_interfaces}"
    )

    existing_loop = get_existing_event_loop()
    created_loop = existing_loop is None
    loop = existing_loop if existing_loop is not None else get_or_create_event_loop()
    loop.set_debug(debug)

    # Prevent more than one process using the same config path from running.
    f = Path(config.path, "spritzled.lock").open(mode="w")
    try:
        try:
            fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as e:
            log.error(f"Another instance of Spritzle is running: {e}")
            log.error("Exiting..")
            sys.exit(1)

        core = Core(
            config,
            state_dir=Path(state_dir) if state_dir else None,
            startup_listen_interfaces=listen_interfaces,
            startup_logfile=logfile,
        )
        bracketed_host = f"[{host}]" if ":" in host and not (host.startswith("[") and host.endswith("]")) else host
        core.key_manager.ensure_local_client_remote(f"http://{bracketed_host}:{port}", core.identity.daemon_id)
        daemon_app = create_app(core, log)
        # Auth middleware is outside setup_app because we don't want it for unit tests
        daemon_app.middlewares.append(auth_middleware)
        try:
            aiohttp.web.run_app(daemon_app, host=host, port=port, loop=loop)
        except OSError as e:
            log.error(f"Failed to bind to {host}:{port}: {e}")
            log.error(f"Check for conflicting services with: ss -tulpn | grep ':{port}'")
            log.error(f"Specify another port with -p / --port (e.g. spritzled -p {port + 1}) or set SPRITZLE_PORT.")
            sys.exit(1)
    finally:
        f.close()
        if created_loop:
            try:
                pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                for t in pending:
                    t.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            finally:
                loop.close()
                asyncio.set_event_loop(None)



@click.group(invoke_without_command=True, context_settings=CONTEXT_SETTINGS)
@click.option(
    "-H",
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host to listen on.",
)
@click.option("--debug", default=False, is_flag=True, help="Enable debug mode.")
@click.option("-p", "--port", default=17382, type=int, show_default=True, help="Port to listen on.")
@click.option(
    "-c",
    "--config-dir",
    "--config_dir",
    "config_dir",
    default=None,
    type=click.Path(),
    help="Configuration directory.",
)
@click.option(
    "-s",
    "--state-dir",
    "--state_dir",
    "state_dir",
    default=None,
    type=click.Path(),
    help="Directory for persistent daemon state (resume data, keys, identity).",
)
@click.option(
    "-l",
    "--log-level",
    default="INFO",
    show_default=True,
    help="Log level.",
)
@click.option(
    "-i",
    "--listen-interfaces",
    "listen_interfaces",
    default=None,
    type=str,
    help="Network interfaces to bind (e.g. 'tun0:6881' or 'wg0:6881').",
)
@click.option(
    "-L",
    "--logfile",
    "--log-file",
    "logfile",
    default=None,
    type=click.Path(),
    help="Path to log file.",
)
@click.pass_context
def main(
    ctx,
    host,
    port,
    debug,
    config_dir,
    state_dir,
    log_level,
    listen_interfaces,
    logfile,
):
    """Spritzle daemon."""
    if ctx.invoked_subcommand is None:
        run_daemon(
            host=host,
            port=port,
            debug=debug,
            config_dir=config_dir,
            state_dir=state_dir,
            log_level=log_level,
            listen_interfaces=listen_interfaces,
            logfile=logfile,
        )


@main.group("key", short_help="Manage API keys.")
def key_group():
    """Manage API keys for the daemon."""
    pass


@key_group.command("create", short_help="Create a new API key.")
@click.option("-n", "--name", default="", help="Name/description for the API key.")
@click.option(
    "-c",
    "--config-dir",
    "--config_dir",
    "config_dir",
    default=None,
    type=click.Path(),
    help="Configuration directory.",
)
@click.option(
    "-s",
    "--state-dir",
    "--state_dir",
    "state_dir",
    default=None,
    type=click.Path(),
    help="State directory.",
)
@click.pass_context
def key_create(ctx, name, config_dir, state_dir):
    """Create a new API key."""
    cfg_dir = config_dir or (ctx.parent.parent.params.get("config_dir") if ctx.parent and ctx.parent.parent else None)
    st_dir = state_dir or (ctx.parent.parent.params.get("state_dir") if ctx.parent and ctx.parent.parent else None)
    config = Config(config_dir=cfg_dir)
    core = Core(config, state_dir=Path(st_dir) if st_dir else None)
    raw_key, meta = core.key_manager.create_key(name=name)
    click.echo(f"Created API key for '{meta['name']}' ({meta['id']}):")
    click.echo(raw_key)


@key_group.command("list", short_help="List API keys.")
@click.option(
    "-c",
    "--config-dir",
    "--config_dir",
    "config_dir",
    default=None,
    type=click.Path(),
    help="Configuration directory.",
)
@click.option(
    "-s",
    "--state-dir",
    "--state_dir",
    "state_dir",
    default=None,
    type=click.Path(),
    help="State directory.",
)
@click.pass_context
def key_list(ctx, config_dir, state_dir):
    """List API keys."""
    cfg_dir = config_dir or (ctx.parent.parent.params.get("config_dir") if ctx.parent and ctx.parent.parent else None)
    st_dir = state_dir or (ctx.parent.parent.params.get("state_dir") if ctx.parent and ctx.parent.parent else None)
    config = Config(config_dir=cfg_dir)
    core = Core(config, state_dir=Path(st_dir) if st_dir else None)
    keys = core.key_manager.list_keys()
    if not keys:
        click.echo("No API keys found.")
        return
    for k in keys:
        status = "active" if k.get("is_active", True) else "revoked"
        click.echo(f"{k['id']}  {k.get('name', 'unnamed'):<15}  {k['prefix']:<14}  {status}")


@key_group.command("revoke", short_help="Revoke an API key.")
@click.argument("key_id_or_name")
@click.option(
    "-c",
    "--config-dir",
    "--config_dir",
    "config_dir",
    default=None,
    type=click.Path(),
    help="Configuration directory.",
)
@click.option(
    "-s",
    "--state-dir",
    "--state_dir",
    "state_dir",
    default=None,
    type=click.Path(),
    help="State directory.",
)
@click.pass_context
def key_revoke(ctx, key_id_or_name, config_dir, state_dir):
    """Revoke an API key by ID or name."""
    cfg_dir = config_dir or (ctx.parent.parent.params.get("config_dir") if ctx.parent and ctx.parent.parent else None)
    st_dir = state_dir or (ctx.parent.parent.params.get("state_dir") if ctx.parent and ctx.parent.parent else None)
    config = Config(config_dir=cfg_dir)
    core = Core(config, state_dir=Path(st_dir) if st_dir else None)
    if core.key_manager.revoke_key(key_id_or_name):
        click.echo(f"Revoked API key: {key_id_or_name}")
    else:
        click.echo(f"API key not found: {key_id_or_name}", err=True)
        sys.exit(1)



