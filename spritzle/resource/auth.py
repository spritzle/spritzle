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
from aiohttp.errors import HttpProcessingError

from spritzle.core import core


async def post_auth(request):
    post = await request.post()

    if post.get('password', None) != core.config['password']:
        raise HttpProcessingError(
            code=401,
            message='Incorrect password')

    payload = {
       'exp': (datetime.utcnow() +
               timedelta(seconds=core.config['auth_timeout']))
    }

    jwt_token = jwt.encode(payload, core.config['auth_secret'], 'HS256')

    return web.json_response({'token': jwt_token.decode('utf8')})
