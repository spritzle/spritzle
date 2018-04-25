#
# spritzle/auth.py
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

from datetime import datetime, timedelta

import jwt
from aiohttp import web

routes = web.RouteTableDef()


@routes.post('/auth')
async def post_auth(request):
    config = request.app['spritzle.config']
    post = await request.post()

    if post.get('password', None) != config['auth_password']:
        raise web.HTTPUnauthorized(reason='Incorrect password')

    payload = {
       'exp': (datetime.utcnow() +
               timedelta(seconds=config['auth_timeout']))
    }

    jwt_token = jwt.encode(payload, config['auth_secret'], 'HS256')

    return web.json_response({'token': jwt_token.decode('utf8')})


async def auth_middleware(app, handler):
    async def middleware(request):
        config = app['spritzle.config']

        peername = request.transport.get_extra_info('peername')
        if peername and peername[0] in config['auth_allow_hosts']:
                return await handler(request)

        if request.rel_url.path == '/auth':
            return await handler(request)

        jwt_token = request.headers.get('authorization', None)
        if jwt_token is None:
            raise web.HTTPUnauthorized(reason='Authorization token required')

        try:
            jwt.decode(
                jwt_token,
                config['auth_secret'],
                algorithms=['HS256'])
        except (jwt.DecodeError, jwt.ExpiredSignatureError):
            raise web.HTTPUnauthorized(reason='Token is invalid')

        return await handler(request)
    return middleware
