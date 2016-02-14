#
# test_settings.py
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

from unittest.mock import MagicMock

from spritzle.main import bootstrap
from spritzle.resource import settings
from spritzle.tests.common import run_until_complete, json_response

bootstrap()


@run_until_complete
async def test_get_settings():
    s, response = await json_response(settings.get_settings(MagicMock()))

    assert isinstance(s, dict)
    assert len(s) > 0


@run_until_complete
async def test_put_settings():
    old, response = await json_response(settings.get_settings(MagicMock()))
    test_key = 'peer_connect_timeout'

    async def json():
        return {test_key: old[test_key] + 1}

    request = MagicMock()
    request.configure_mock(**{
        'json.return_value': json(),
    })

    response = await settings.put_settings(request)
    assert response.status == 200

    new, response = await json_response(settings.get_settings(MagicMock()))

    assert old[test_key] != new[test_key]
    assert old[test_key] == new[test_key] - 1
