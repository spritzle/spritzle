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

import pytest
from datetime import datetime, timedelta

import aiohttp
import jwt

import spritzle.tests.common
from spritzle.tests.common import run_until_complete, json_response
from spritzle.resource import auth


async def create_mock_request(core=None, password=None, config=None):
    async def post():
        return {
            'password': password,
        }

    request = await spritzle.tests.common.create_mock_request(core=core, config=config)
    request.post = post
    return request


@run_until_complete
async def test_post_auth(core):
    config = {
        'auth_password': 'password',
        'auth_timeout': 120,
        'auth_secret': 'secret',
        'auth_allowed_hosts': [],
    }

    _, response = await json_response(
        auth.post_auth(await create_mock_request(core, 'password', config)))
    assert response.status == 200
    with pytest.raises(aiohttp.web.HTTPUnauthorized):
        _, response = await json_response(
            auth.post_auth(await create_mock_request(core, 'badpassword', config)))
        assert response.status == 401


@run_until_complete
async def test_auth_middleware(core):
    async def handler(request):
        request.handled = True

    request = await create_mock_request(core)
    request.headers = {}
    request.handled = False
    request.rel_url.path = '/auth'

    mw = await auth.auth_middleware(request.app, handler)
    await mw(request)
    assert request.handled

    request.handled = False
    request.rel_url.path = '/'

    with pytest.raises(aiohttp.web.HTTPUnauthorized) as e:
        await mw(request)
        assert e.exception.reason == 'Authorization token required'

    request.headers['authorization'] = 'badtoken'

    with pytest.raises(aiohttp.web.HTTPUnauthorized) as e:
        await mw(request)
        assert e.exception.reason == 'Token is invalid'

    config = {
        'auth_secret': 'secret',
        'auth_allow_hosts': [],
    }
    payload = {
        'exp': (datetime.utcnow() + timedelta(seconds=120))
    }
    token = jwt.encode(payload, config['auth_secret'], 'HS256').decode('utf8')
    request.headers['authorization'] = token
    request.app['spritzle.config'] = config
    await mw(request)
    assert request.handled


@run_until_complete
async def test_auth_allow_hosts(core):
    async def handler(request):
        request.handled = True

    request = await create_mock_request(core)
    request.headers = {}
    request.handled = False
    request.rel_url.path = '/'
    request.transport.get_extra_info.return_value = ('127.0.0.1', 12345)

    mw = await auth.auth_middleware(request.app, handler)
    await mw(request)
    assert request.handled

    request.handled = False
    request.transport.get_extra_info.return_value = ('128.8.8.8', 12345)
    with pytest.raises(aiohttp.web.HTTPUnauthorized) as e:
        await mw(request)
        assert e.exception.reason == 'Authorization token required'
