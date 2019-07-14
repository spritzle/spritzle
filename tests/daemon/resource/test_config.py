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


async def test_get_config(core, cli):
    config_data = {"key1": "value1"}
    core.config.data = config_data
    response = await cli.get("/config")
    data = await response.json()

    assert data == config_data


async def test_put_config(core, cli):
    orig_config = {"key1": "value1"}
    new_config = {"key2": "value2"}
    core.config.data = orig_config

    response = await cli.put("/config", json=new_config)
    assert response.status == 200
    assert core.config.data == new_config


async def test_patch_config(core, cli):
    orig_config = {"key1": "value1"}
    patch_config = {"key2": "value2"}
    new_config = {**orig_config, **patch_config}
    core.config.data = orig_config

    response = await cli.patch("/config", json=patch_config)
    assert response.status == 200
    assert core.config.data == new_config
