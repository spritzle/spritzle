#
# test_session.py
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


async def test_get_session_stats(cli):
    response = await cli.get("/session/stats")
    s = await response.json()
    assert isinstance(s, dict)
    assert len(s) > 0


async def test_get_session_dht(cli):
    response = await cli.get("/session/dht")
    b = await response.json()
    assert isinstance(b, bool)


async def test_get_settings(cli):
    response = await cli.get("/session/settings")
    s = await response.json()
    assert isinstance(s, dict)
    assert len(s) > 0


async def test_put_settings(cli):
    response = await cli.get("/session/settings")
    old = await response.json()
    test_key = "peer_connect_timeout"

    response = await cli.put("/session/settings", json={test_key: old[test_key] + 1})
    assert response.status == 200

    response = await cli.get("/session/settings")
    new = await response.json()

    assert old[test_key] != new[test_key]
    assert old[test_key] == new[test_key] - 1


async def test_put_settings_bad_key(cli):
    response = await cli.put("/session/settings", json={"bad_key": 1})
    assert response.status == 400


async def test_put_settings_type_coercion(cli):
    response = await cli.put("/session/settings", json={"peer_connect_timeout": "1"})
    assert response.status == 200


async def test_put_settings_boolean_coercion(cli):
    # Set to True first
    response = await cli.put("/session/settings", json={"enable_dht": True})
    assert response.status == 200
    response = await cli.get("/session/settings")
    assert (await response.json())["enable_dht"] is True

    # Now attempt to set to False using string "false"
    response = await cli.put("/session/settings", json={"enable_dht": "false"})
    assert response.status == 200
    response = await cli.get("/session/settings")
    assert (await response.json())["enable_dht"] is False

    # Also test "0" and "no"
    await cli.put("/session/settings", json={"enable_dht": True})
    response = await cli.put("/session/settings", json={"enable_dht": "0"})
    assert response.status == 200
    response = await cli.get("/session/settings")
    assert (await response.json())["enable_dht"] is False


async def test_put_settings_incompatible_type(cli):
    response = await cli.put(
        "/session/settings", json={"peer_connect_timeout": "not_an_int"}
    )
    assert response.status == 400


async def test_get_session_stats_timeout(cli, monkeypatch):
    import asyncio
    from spritzle.daemon.keys import APP_KEY_CORE

    core = cli.app[APP_KEY_CORE]

    async def mock_timeout_stats():
        raise asyncio.TimeoutError()

    monkeypatch.setattr(core, "get_session_stats", mock_timeout_stats)
    response = await cli.get("/session/stats")
    assert response.status == 504


async def test_get_settings_defaults(cli):
    response = await cli.get("/session/settings/defaults")
    assert response.status == 200
    defaults = await response.json()
    assert isinstance(defaults, dict)
    assert len(defaults) > 200
    assert "user_agent" in defaults
    assert "download_rate_limit" in defaults


async def test_get_settings_modified_filter(cli):
    # First reset all
    await cli.post("/session/settings/reset", json={"all": True})

    # None modified initially
    resp = await cli.get("/session/settings?modified=true")
    assert resp.status == 200
    assert await resp.json() == {}

    # Modify one setting
    await cli.put("/session/settings", json={"download_rate_limit": 500000})

    resp = await cli.get("/session/settings?modified=true")
    assert resp.status == 200
    modified = await resp.json()
    assert "download_rate_limit" in modified
    assert modified["download_rate_limit"] == 500000
    assert len(modified) == 1

    # Reset
    await cli.post("/session/settings/reset", json={"keys": ["download_rate_limit"]})
    resp = await cli.get("/session/settings?modified=true")
    assert await resp.json() == {}


async def test_post_settings_reset_keys(cli):
    defaults_resp = await cli.get("/session/settings/defaults")
    defaults = await defaults_resp.json()
    default_limit = defaults["download_rate_limit"]

    # Change download_rate_limit
    await cli.put("/session/settings", json={"download_rate_limit": default_limit + 1000})
    curr = await (await cli.get("/session/settings")).json()
    assert curr["download_rate_limit"] == default_limit + 1000

    # Reset it
    resp = await cli.post("/session/settings/reset", json={"keys": ["download_rate_limit"]})
    assert resp.status == 200
    assert (await resp.json())["reset"] == ["download_rate_limit"]

    # Verify restored to default
    after = await (await cli.get("/session/settings")).json()
    assert after["download_rate_limit"] == default_limit


async def test_post_settings_reset_all(cli):
    defaults_resp = await cli.get("/session/settings/defaults")
    defaults = await defaults_resp.json()

    # Change two settings
    await cli.put("/session/settings", json={"download_rate_limit": 12345, "upload_rate_limit": 54321})

    # Reset all
    resp = await cli.post("/session/settings/reset", json={"all": True})
    assert resp.status == 200
    reset_list = (await resp.json())["reset"]
    assert len(reset_list) > 200

    # Verify both restored
    curr = await (await cli.get("/session/settings")).json()
    assert curr["download_rate_limit"] == defaults["download_rate_limit"]
    assert curr["upload_rate_limit"] == defaults["upload_rate_limit"]


async def test_post_settings_reset_invalid_key(cli):
    resp = await cli.post("/session/settings/reset", json={"keys": ["nonexistent_setting_xyz"]})
    assert resp.status == 400
    err = await resp.text()
    assert "nonexistent_setting_xyz" in err


async def test_post_settings_reset_bad_payload(cli):
    resp = await cli.post("/session/settings/reset", json={})
    assert resp.status == 400

    resp = await cli.post("/session/settings/reset", data="invalid json")
    assert resp.status == 400


async def test_get_session_profiles(cli):
    resp = await cli.get("/session/profiles")
    assert resp.status == 200
    profiles = await resp.json()
    assert "deluge-2.1.1" in profiles
    assert "qbittorrent-4.6.5" in profiles
    assert "transmission-4.0.5" in profiles
    assert profiles["deluge-2.1.1"]["peer_fingerprint"] == "-DE2110-"


async def test_put_settings_profile(cli):
    resp = await cli.put("/session/settings", json={"profile": "deluge-2.1.1"})
    assert resp.status == 200

    resp = await cli.get("/session/settings")
    settings = await resp.json()
    assert settings["user_agent"] == "Deluge/2.1.1 libtorrent/2.0.10.0"
    assert settings["peer_fingerprint"] == "-DE2110-"

    # Test invalid profile
    resp = await cli.put("/session/settings", json={"profile": "invalid-profile-xyz"})
    assert resp.status == 400
    err = await resp.text()
    assert "Unknown profile" in err


async def test_put_settings_peer_id(cli):
    resp = await cli.put("/session/settings", json={"peer_id": "-TR4050-123456789012"})
    assert resp.status == 200

    resp = await cli.get("/session/settings")
    settings = await resp.json()
    assert settings["peer_fingerprint"] == "-TR4050-"


async def test_put_settings_listen_interfaces(cli):
    resp = await cli.put("/session/settings", json={"listen_interfaces": "127.0.0.1:6881"})
    assert resp.status == 200

    resp = await cli.get("/session/settings")
    settings = await resp.json()
    assert "127.0.0.1:6881" in settings["listen_interfaces"]



