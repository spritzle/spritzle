#
# test_config.py
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

from spritzle.resource import config
from spritzle.tests.common import (
    run_until_complete, json_response, create_mock_request)


@run_until_complete
async def test_get_config(core):
    config_data = {"key1": "value1"}
    request = await create_mock_request(core=core, config=config_data)
    s, response = await json_response(config.get_config(request))

    assert s == config_data


@run_until_complete
async def test_put_config(core):
    orig_config = {"key1": "value1"}
    new_config = {"key2": "value2"}
    request = await create_mock_request(core=core, config=orig_config)

    async def json():
        return new_config

    request.configure_mock(**{
        'json.return_value': json(),
    })

    response = await config.put_config(request)
    assert response.status == 200

    s, response = await json_response(config.get_config(request))

    assert s == new_config

@run_until_complete
async def test_patch_config(core):
    orig_config = {"key1": "value1"}
    patch_config = {"key2": "value2"}
    new_config = {**orig_config, **patch_config}
    request = await create_mock_request(core=core, config=orig_config)

    async def json():
        return patch_config

    request.configure_mock(**{
        'json.return_value': json(),
    })

    response = await config.patch_config(request)
    assert response.status == 200

    s, response = await json_response(config.get_config(request))

    assert s == new_config
