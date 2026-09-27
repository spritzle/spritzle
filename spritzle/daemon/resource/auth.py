#
# spritzle/daemon/resource/auth.py
#
# Copyright (C) 2016-2026 Andrew Resch <andrewresch@gmail.com>
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

import importlib.metadata
from json import JSONDecodeError
import time
from typing import Any

from aiohttp import web

from spritzle.daemon.keys import (
    APP_KEY_CORE,
    APP_KEY_IDENTITY,
    APP_KEY_KEY_MANAGER,
    REQ_KEY_AUTH_IDENTITY,
)

routes = web.RouteTableDef()


@routes.get("/status")
async def get_status(request: web.Request) -> web.Response:
    """Returns daemon status, identity, version, uptime, and high-level stats."""
    core = request.app.get(APP_KEY_CORE)
    identity = request.app.get(APP_KEY_IDENTITY) or (core.identity if core else None)
    daemon_id = identity.daemon_id if identity else "unknown"

    try:
        version = importlib.metadata.version("spritzle")
    except Exception:
        version = "1.0.0"

    uptime = round(time.time() - core.start_time, 1) if (core and hasattr(core, "start_time")) else 0.0
    num_torrents = len(core.session.get_torrents()) if (core and core.session) else 0

    return web.json_response({
        "status": "ok",
        "daemon_id": daemon_id,
        "version": version,
        "uptime": uptime,
        "num_torrents": num_torrents,
    })


@routes.get("/keys")
async def get_keys(request: web.Request) -> web.Response:
    """Lists all active and revoked API keys."""
    core = request.app.get(APP_KEY_CORE)
    key_manager = request.app.get(APP_KEY_KEY_MANAGER) or (core.key_manager if core else None)
    if not key_manager:
        raise web.HTTPInternalServerError(reason="Key manager not initialized")
    return web.json_response(key_manager.list_keys())


@routes.post("/keys")
async def post_keys(request: web.Request) -> web.Response:
    """Creates a new API key."""
    core = request.app.get(APP_KEY_CORE)
    key_manager = request.app.get(APP_KEY_KEY_MANAGER) or (core.key_manager if core else None)
    if not key_manager:
        raise web.HTTPInternalServerError(reason="Key manager not initialized")

    name = ""
    if request.can_read_body:
        try:
            body = await request.json()
            if isinstance(body, dict):
                name = str(body.get("name", ""))
        except (JSONDecodeError, UnicodeDecodeError):
            pass

    raw_key, meta = key_manager.create_key(name=name)
    return web.json_response({"key": raw_key, **meta}, status=201)


@routes.delete("/keys/{id}")
async def delete_key(request: web.Request) -> web.Response:
    """Revokes an API key by its ID or name."""
    core = request.app.get(APP_KEY_CORE)
    key_manager = request.app.get(APP_KEY_KEY_MANAGER) or (core.key_manager if core else None)
    if not key_manager:
        raise web.HTTPInternalServerError(reason="Key manager not initialized")

    key_id = request.match_info["id"]
    revoked = key_manager.revoke_key(key_id)
    if not revoked:
        raise web.HTTPNotFound(reason="Key not found")
    return web.json_response({"revoked": True})


@web.middleware
async def auth_middleware(request: web.Request, handler: Any) -> web.Response:
    core = request.app.get(APP_KEY_CORE)
    identity = request.app.get(APP_KEY_IDENTITY) or (core.identity if core else None)
    daemon_id = identity.daemon_id if identity else ""

    api_key = request.headers.get("x-api-key")
    if not api_key:
        auth_header = request.headers.get("authorization")
        if auth_header:
            if auth_header.lower().startswith("bearer "):
                api_key = auth_header[7:].strip()
            else:
                api_key = auth_header.strip()

    if not api_key:
        raise web.HTTPUnauthorized(reason="Authorization key required")

    key_manager = request.app.get(APP_KEY_KEY_MANAGER) or (core.key_manager if core else None)
    key_info = key_manager.verify_key(api_key) if key_manager else None
    if key_info is None:
        raise web.HTTPUnauthorized(reason="API key is invalid or revoked")

    request[REQ_KEY_AUTH_IDENTITY] = key_info
    response = await handler(request)
    if daemon_id:
        response.headers["X-Spritzle-Daemon-Id"] = daemon_id
    return response
