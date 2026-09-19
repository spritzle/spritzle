#
# spritzle/session.py
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
from aiohttp import web

from spritzle.daemon.keys import APP_KEY_CORE

routes = web.RouteTableDef()


@routes.get("/session/settings")
async def get_session_settings(request):
    core = request.app[APP_KEY_CORE]
    settings = core.session.get_settings()
    modified = request.query.get("modified", "").strip().lower() in ("true", "1", "yes", "on")
    if modified:
        baseline = core.get_baseline_settings()
        settings = {k: v for k, v in settings.items() if k in baseline and v != baseline[k]}
    return web.json_response(settings)


@routes.get("/session/settings/defaults")
async def get_session_settings_defaults(request):
    core = request.app[APP_KEY_CORE]
    return web.json_response(core.get_baseline_settings())


@routes.post("/session/settings/reset")
async def post_session_settings_reset(request):
    core = request.app[APP_KEY_CORE]
    try:
        data = await request.json()
    except Exception as e:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        raise web.HTTPBadRequest(reason="Request body must be a JSON object.")

    reset_all = bool(data.get("all", False))
    keys = data.get("keys")

    if not reset_all and not keys:
        raise web.HTTPBadRequest(reason="Must specify 'keys' list or 'all: true'.")

    if keys is not None and not isinstance(keys, list):
        raise web.HTTPBadRequest(reason="'keys' must be a list of setting names.")

    try:
        reset_keys = core.reset_settings(keys=keys, reset_all=reset_all)
    except (KeyError, ValueError) as e:
        raise web.HTTPBadRequest(reason=str(e))

    return web.json_response({"reset": reset_keys})


@routes.put("/session/settings")
async def put_session_settings(request):
    core = request.app[APP_KEY_CORE]
    try:
        settings = await request.json()
    except Exception as e:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {e}")

    if not isinstance(settings, dict):
        raise web.HTTPBadRequest(reason="Request body must be a JSON object.")

    current = core.session.get_settings()

    # Do our best to coerce what the client sent into the proper types that
    # libtorrent expects.
    for key, value in current.items():
        if key in settings and type(settings[key]) is not type(value):
            if settings[key] is None:
                raise web.HTTPBadRequest(
                    reason=f"Setting '{key}' does not allow null values."
                )
            if isinstance(value, bool):
                val_str = str(settings[key]).strip().lower()
                if val_str in ("true", "1", "yes", "on"):
                    settings[key] = True
                elif val_str in ("false", "0", "no", "off", ""):
                    settings[key] = False
                else:
                    raise web.HTTPBadRequest(
                        reason=f"Cannot coerce value '{settings[key]}' to boolean for setting '{key}'."
                    )
            else:
                try:
                    settings[key] = type(value)(settings[key])
                except (ValueError, TypeError) as e:
                    raise web.HTTPBadRequest(
                        reason=f"Cannot coerce value '{settings[key]}' for setting '{key}': {e}"
                    )

    try:
        core.session.apply_settings(settings)
    except (KeyError, RuntimeError, TypeError, ValueError) as e:
        raise web.HTTPBadRequest(reason=str(e))
    return web.json_response()



@routes.get("/session/stats")
async def get_session_stats(request):
    core = request.app[APP_KEY_CORE]
    try:
        stats = await core.get_session_stats()
    except asyncio.TimeoutError:
        raise web.HTTPGatewayTimeout(reason="Timed out waiting for session stats")
    return web.json_response(stats)


@routes.get("/session/dht")
async def get_session_dht(request):
    core = request.app[APP_KEY_CORE]
    return web.json_response(core.session.is_dht_running())
