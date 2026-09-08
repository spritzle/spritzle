#
# spritzle/config.py
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

from aiohttp import web


from spritzle.daemon.keys import APP_KEY_CONFIG

routes = web.RouteTableDef()


SECRET_KEYS = {"auth_password", "auth_secret"}


@routes.get("/config")
async def get_config(request):
    config = request.app[APP_KEY_CONFIG]
    safe_config = {k: v for k, v in config.items() if k not in SECRET_KEYS}
    return web.json_response(safe_config)


@routes.put("/config")
async def put_config(request):
    config = request.app[APP_KEY_CONFIG]
    try:
        new_values = await request.json()
    except Exception as e:
        raise web.HTTPBadRequest(text=f"Invalid JSON body: {e}")

    if not isinstance(new_values, dict):
        raise web.HTTPBadRequest(text="Request body must be a JSON object.")

    saved_secrets = {k: config[k] for k in SECRET_KEYS if k in config}
    backup_items = dict(config.items())
    config.reset()
    try:
        config.update(saved_secrets)
        config.update(new_values)
    except (ValueError, TypeError, RuntimeError) as e:
        config.reset()
        try:
            config.update(backup_items)
        except Exception:
            pass
        raise web.HTTPBadRequest(reason=f"Failed to update config: {e}")
    return web.Response()


@routes.patch("/config")
async def patch_config(request):
    config = request.app[APP_KEY_CONFIG]
    try:
        new_values = await request.json()
    except Exception as e:
        raise web.HTTPBadRequest(text=f"Invalid JSON body: {e}")

    if not isinstance(new_values, dict):
        raise web.HTTPBadRequest(text="Request body must be a JSON object.")

    backup_items = {k: config[k] for k in new_values if k in config}
    new_keys = [k for k in new_values if k not in config]
    try:
        config.update(new_values)
    except (ValueError, TypeError, RuntimeError) as e:
        for k in new_keys:
            if k in config:
                try:
                    del config[k]
                except Exception:
                    pass
        try:
            config.update(backup_items)
        except Exception:
            pass
        raise web.HTTPBadRequest(reason=f"Failed to update config: {e}")
    return web.Response()


