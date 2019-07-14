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

import aiohttp.web
import pytest
from unittest.mock import patch


@pytest.fixture
def cli(loop, core, app, aiohttp_client):
    async def get_error(request):
        # HTTPException doesn't like being instantiated without a status_code
        with patch("aiohttp.web.HTTPException.status_code", 0):
            exception = aiohttp.web.HTTPException()
            exception.set_status(request.query["status"], request.query["reason"])
            exception.text = request.query["message"]
            raise exception

    async def get_unexpected_error(request):
        raise Exception()

    async def get_no_error(request):
        raise aiohttp.web.HTTPOk(text="No Error")

    app.router.add_route("GET", "/expected_error", get_error)
    app.router.add_route("GET", "/unexpected_error", get_unexpected_error)
    app.router.add_route("GET", "/no_error", get_no_error)
    return loop.run_until_complete(aiohttp_client(app))


@pytest.mark.parametrize(
    "error_params",
    [
        {"status": 404, "reason": "not there", "message": "aoeu"},
        {"status": 400, "reason": "other thing", "message": "blah\nblah"},
    ],
)
async def test_expected_error(cli, error_params):
    response = await cli.get("/expected_error", params=error_params)
    assert response.content_type == "application/json"
    assert response.status == error_params["status"]
    assert response.reason == error_params["reason"]
    body = await response.json()
    assert body == error_params


async def test_unexpected_error(cli):
    response = await cli.get("/unexpected_error")
    assert response.content_type == "application/json"
    assert response.status == 500
    body = await response.json()
    assert body["status"] == 500


async def test_no_error(cli):
    """
    Make sure error handler isn't mangling success responses.
    """
    response = await cli.get("/no_error")
    assert response.content_type == "text/plain"
    assert (await response.text()) == "No Error"
