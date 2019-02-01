#
# test_auth.py
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

import aiohttp
import pytest

from spritzle.resource import auth


@pytest.fixture
def cli(loop, core, app, aiohttp_client):
    config = {
        'auth_password': 'password',
        'auth_timeout': 120,
        'auth_secret': 'secret',
        'auth_allow_hosts': [],
    }
    core.config.data = config

    async def get_nothing(request):
        return aiohttp.web.Response()

    app.router.add_route('GET', '/', get_nothing)
    app.middlewares.append(auth.auth_middleware)
    return loop.run_until_complete(aiohttp_client(app))


async def test_post_auth(core, cli):
    config = {
        'auth_password': 'password',
        'auth_timeout': 120,
        'auth_secret': 'secret',
        'auth_allowed_hosts': [],
    }
    core.config.data = config
    response = await cli.post('/auth', json={'password': 'password'})
    assert response.status == 200

    response = await cli.post('/auth', json={'password': 'badpassword'})
    assert response.status == 401


async def test_auth_middleware(cli):
    response = await cli.get('/')
    assert response.status == 401
    assert response.reason == 'Authorization token required'

    response = await cli.get('/', headers={'authorization': 'badtoken'})
    assert response.status == 401
    assert response.reason == 'Token is invalid'

    response = await cli.post('/auth', json={'password': 'password'})
    data = await response.json()
    token = data['token']

    response = await cli.get('/', headers={'authorization': token})
    assert response.status == 200


async def test_auth_allow_hosts(core, cli):
    core.config['auth_allow_hosts'] = []

    response = await cli.get('/')
    assert response.status == 401

    core.config['auth_allow_hosts'] = ['127.0.0.1']

    response = await cli.get('/')
    assert response.status == 200
