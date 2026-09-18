#
# test_auth.py
#
# Copyright (C) 2016-2026 Andrew Resch <andrewresch@gmail.com>
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

from aiohttp import web
import pytest

from spritzle.daemon.keys import APP_KEY_CORE, APP_KEY_IDENTITY, APP_KEY_KEY_MANAGER
from spritzle.daemon.resource import auth


@pytest.fixture
def cli(loop, core, app, aiohttp_client):
    app[APP_KEY_CORE] = core
    app[APP_KEY_IDENTITY] = core.identity
    app[APP_KEY_KEY_MANAGER] = core.key_manager

    async def get_nothing(request):
        return web.Response(text="ok")

    app.router.add_routes(auth.routes)
    app.router.add_route("GET", "/", get_nothing)
    app.middlewares.append(auth.auth_middleware)
    return loop.run_until_complete(aiohttp_client(app))


async def test_get_status_authenticated(cli, core):
    raw_key, _ = core.key_manager.create_key(name="admin")
    response = await cli.get("/status", headers={"Authorization": f"Bearer {raw_key}"})
    assert response.status == 200
    data = await response.json()
    assert data["status"] == "ok"
    assert data["daemon_id"] == core.identity.daemon_id
    assert "version" in data
    assert "uptime" in data
    assert "num_torrents" in data
    assert response.headers.get("X-Spritzle-Daemon-Id") == core.identity.daemon_id


async def test_get_status_unauthenticated(cli):
    response = await cli.get("/status")
    assert response.status == 401
    assert "X-Spritzle-Daemon-Id" not in response.headers


async def test_auth_middleware_missing_key(cli):
    response = await cli.get("/")
    assert response.status == 401
    assert response.reason == "Authorization key required"
    assert "X-Spritzle-Daemon-Id" not in response.headers


async def test_auth_middleware_invalid_key(cli):
    response = await cli.get("/", headers={"authorization": "invalid_key"})
    assert response.status == 401
    assert response.reason == "API key is invalid or revoked"
    assert "X-Spritzle-Daemon-Id" not in response.headers


async def test_auth_middleware_valid_bearer_key(cli, core):
    raw_key, _ = core.key_manager.create_key(name="test_bearer")
    response = await cli.get("/", headers={"authorization": f"Bearer {raw_key}"})
    assert response.status == 200
    assert await response.text() == "ok"
    assert response.headers.get("X-Spritzle-Daemon-Id") == core.identity.daemon_id


async def test_auth_middleware_x_api_key_header(cli, core):
    raw_key, _ = core.key_manager.create_key(name="test_header")
    response = await cli.get("/", headers={"x-api-key": raw_key})
    assert response.status == 200
    assert await response.text() == "ok"
    assert response.headers.get("X-Spritzle-Daemon-Id") == core.identity.daemon_id


async def test_keys_crud_and_revocation(cli, core):
    # Create key through API (using existing valid key to authenticate)
    admin_key, _ = core.key_manager.create_key(name="admin")
    headers = {"Authorization": f"Bearer {admin_key}"}

    create_resp = await cli.post("/keys", json={"name": "sonarr"}, headers=headers)
    assert create_resp.status == 201
    create_data = await create_resp.json()
    sonarr_key = create_data["key"]
    sonarr_id = create_data["id"]
    assert sonarr_key.startswith("spritzle_")

    # Sonarr key can authenticate
    test_resp = await cli.get("/", headers={"Authorization": f"Bearer {sonarr_key}"})
    assert test_resp.status == 200

    # List keys
    list_resp = await cli.get("/keys", headers=headers)
    assert list_resp.status == 200
    key_list = await list_resp.json()
    assert any(k["id"] == sonarr_id for k in key_list)

    # Revoke key
    del_resp = await cli.delete(f"/keys/{sonarr_id}", headers=headers)
    assert del_resp.status == 200

    # Revoked key is rejected
    test_revoked = await cli.get("/", headers={"Authorization": f"Bearer {sonarr_key}"})
    assert test_revoked.status == 401
    assert test_revoked.reason == "API key is invalid or revoked"
    assert "X-Spritzle-Daemon-Id" not in test_revoked.headers


async def test_revoke_nonexistent_key(cli, core):
    admin_key, _ = core.key_manager.create_key(name="admin")
    headers = {"Authorization": f"Bearer {admin_key}"}
    response = await cli.delete("/keys/nonexistent_key_id", headers=headers)
    assert response.status == 404


async def test_local_client_discovery(core):
    data = core.key_manager.ensure_local_client_remote("http://127.0.0.1:8080", core.identity.daemon_id)
    assert data["name"] == "local"
    assert data["url"] == "http://127.0.0.1:8080"
    assert data["daemon_id"] == core.identity.daemon_id
    assert data["api_key"].startswith("spritzle_")
    assert core.key_manager.verify_key(data["api_key"]) is not None
