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
    core.config["key1"] = "value1"
    response = await cli.get("/config")
    data = await response.json()

    assert "key1" in data
    assert data["key1"] == "value1"


async def test_put_config(core, cli):
    core.config["key1"] = "value1"
    new_config = {"key2": "value2"}

    response = await cli.put("/config", json=new_config)
    assert response.status == 200
    assert core.config["key2"] == "value2"
    assert "key1" not in core.config


async def test_put_config_preserves_secrets(core, cli):
    core.config["auth_password"] = "custom_password"
    core.config["auth_secret"] = "custom_secret"
    new_config = {"key2": "value2"}

    response = await cli.put("/config", json=new_config)
    assert response.status == 200
    assert core.config["auth_password"] == "custom_password"
    assert core.config["auth_secret"] == "custom_secret"


async def test_patch_config(core, cli):
    core.config["key1"] = "value1"
    patch_config = {"key2": "value2"}

    response = await cli.patch("/config", json=patch_config)
    assert response.status == 200
    assert core.config["key1"] == "value1"
    assert core.config["key2"] == "value2"


async def test_get_config_redacts_secrets(core, cli):
    core.config["auth_password"] = "supersecret"
    core.config["auth_secret"] = "myjwtsecret"
    response = await cli.get("/config")
    data = await response.json()
    assert "auth_password" not in data or data["auth_password"] != "supersecret"
    assert "auth_secret" not in data or data["auth_secret"] != "myjwtsecret"


async def test_put_config_invalid_body(core, cli):
    core.config["key1"] = "value1"
    response = await cli.put("/config", data="not json")
    assert response.status == 400
    assert core.config["key1"] == "value1"


async def test_put_config_update_error_returns_400(core, cli, monkeypatch):
    def mock_setitem(self, key, value):
        raise ValueError(f"Value is not JSON serializable: {value}")

    monkeypatch.setattr("spritzle.daemon.db.DB.__setitem__", mock_setitem)
    response = await cli.put("/config", json={"key": "val"})
    assert response.status == 400


async def test_put_config_update_error_preserves_existing_config(core, cli, monkeypatch):
    core.config["key1"] = "value1"
    real_setitem = type(core.config).__setitem__

    def failing_setitem(self, key, value):
        if key == "bad_key":
            raise ValueError(f"Value is not JSON serializable: {value}")
        real_setitem(self, key, value)

    monkeypatch.setattr(type(core.config), "__setitem__", failing_setitem)
    response = await cli.put("/config", json={"bad_key": "bad_val"})
    assert response.status == 400
    assert core.config.get("key1") == "value1"


