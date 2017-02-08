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

from unittest.mock import MagicMock, patch
from nose.tools import assert_raises

import aiohttp.errors

from spritzle.tests.common import run_until_complete, json_response
from spritzle.resource import auth


def create_mock_request(password=None):
    async def post():
        return {
            'password': password,
        }

    request = MagicMock()
    request.post = post
    return request


@run_until_complete
async def test_post_auth():
    config = {
        'password': 'password',
        'auth_timeout': 120,
        'auth_secret': 'secret',
    }

    with patch('spritzle.core.core.config', config):
        _, response = await json_response(
            auth.post_auth(create_mock_request('password')))
        assert response.status == 200
        with assert_raises(aiohttp.errors.HttpProcessingError) as e:
            await json_response(
                auth.post_auth(create_mock_request('badpassword')))
        assert e.exception.code == 401
