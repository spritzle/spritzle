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

routes = web.RouteTableDef()


@routes.get('/config')
async def get_config(request):
    config = request.app['spritzle.config']
    return web.json_response(dict(config))


@routes.put('/config')
async def put_config(request):
    config = request.app['spritzle.config']
    new_values = await request.json()
    config.data = new_values
    config.save()
    return web.Response()


@routes.patch('/config')
async def patch_config(request):
    config = request.app['spritzle.config']
    new_values = await request.json()
    config.update(new_values)
    config.save()
    return web.Response()
