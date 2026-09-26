#
# spritzle/daemon/resource/log.py
#
# Copyright (C) 2026 Andrew Resch <andrewresch@gmail.com>
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

import time
from typing import Optional

from aiohttp import web

from ..logger import get_log_buffer_handler

routes = web.RouteTableDef()


@routes.get("/log")
async def get_logs(request: web.Request) -> web.Response:
    """Retrieve filtered log entries from the in-memory log buffer."""
    query = request.query
    level = query.get("level")
    regex = query.get("regex")
    raw_since = query.get("since")
    raw_limit = query.get("limit")

    since: Optional[float] = None
    if raw_since:
        try:
            val = float(raw_since)
            if val > 1e8:
                since = val
            elif val > 0:
                since = time.time() - val
            else:
                since = time.time() + val
        except ValueError:
            raise web.HTTPBadRequest(reason=f"Invalid since parameter: {raw_since}")

    limit: Optional[int] = 100
    if raw_limit:
        try:
            limit = int(raw_limit)
            if limit <= 0:
                raise ValueError()
            if limit > 1000:
                limit = 1000
        except ValueError:
            raise web.HTTPBadRequest(reason=f"Invalid limit parameter: {raw_limit}")

    handler = get_log_buffer_handler()
    try:
        logs = handler.get_logs(level=level, regex=regex, since=since, limit=limit)
    except ValueError as ex:
        raise web.HTTPBadRequest(reason=str(ex))

    return web.json_response(logs)


@routes.delete("/log")
async def clear_logs(request: web.Request) -> web.Response:
    """Clear all entries in the in-memory log buffer."""
    handler = get_log_buffer_handler()
    handler.clear()
    return web.json_response({"status": "cleared"})
