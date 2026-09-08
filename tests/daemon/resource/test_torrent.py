#
# test_torrent.py
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

import asyncio
from base64 import b64encode
from pathlib import Path
from unittest.mock import MagicMock

import libtorrent as lt
import pytest

from spritzle.daemon.resource import torrent
from ..common import torrent_dir


def create_torrent_post_data(filename=None, tags=None, **kwargs):
    post = {"flags": lt.torrent_flags.paused}
    post.update(kwargs)

    if filename:
        filepath = Path(torrent_dir, filename)
        post["file"] = b64encode(filepath.open(mode="rb").read()).decode("ascii")

    if tags:
        post["spritzle.tags"] = tags

    return post


async def test_get_torrent(cli):
    await test_post_torrent(cli)

    response = await cli.get("/torrent")
    torrents = await response.json()
    assert isinstance(torrents, list)
    assert len(torrents) > 0

    info_hash = "44a040be6d74d8d290cd20128788864cbf770719"

    response = await cli.get(f"/torrent/{info_hash}")
    ts = await response.json()
    assert isinstance(ts, dict)
    assert ts["info_hash"] == info_hash
    assert ts["spritzle.tags"] == ["foo"]

    response = await cli.get("/torrent/" + "a0" * 20)
    assert response.status == 404


async def test_get_torrent_query(cli):
    info_hash = await test_post_torrent(cli)

    response = await cli.get("/torrent?info_hash=^44a0.*$")
    assert response.status == 200

    torrents = await response.json()
    assert torrents == [info_hash]

    response = await cli.get("/torrent?info_hash=^64a0.*$")
    assert response.status == 200

    torrents = await response.json()
    assert len(torrents) == 0

    response = await cli.get("/torrent?block_size.gt=0")
    assert response.status == 200
    torrents = await response.json()
    assert len(torrents) == 1

    response = await cli.get("/torrent?block_size.lt=16384")
    assert response.status == 200
    torrents = await response.json()
    assert len(torrents) == 0

    response = await cli.get("/torrent?block_size=16384")
    assert response.status == 200
    torrents = await response.json()
    assert len(torrents) == 1

    response = await cli.get("/torrent?unknown_field=foo")
    assert response.status == 400


async def test_get_torrent_query_by_tags(cli):
    post_data = create_torrent_post_data(
        filename="random_one_file.torrent", tags=["linux", "iso"]
    )
    resp = await cli.post("/torrent", json=post_data)
    assert resp.status == 201
    info_hash = (await resp.json())["info_hash"]

    # Query with exact tag
    resp = await cli.get("/torrent?spritzle.tags=linux")
    assert resp.status == 200
    assert (await resp.json()) == [info_hash]

    # Query with non-matching tag
    resp = await cli.get("/torrent?spritzle.tags=windows")
    assert resp.status == 200
    assert (await resp.json()) == []

    # Query with any
    resp = await cli.get("/torrent?spritzle.tags.any=lin.*")
    assert resp.status == 200
    assert (await resp.json()) == [info_hash]

    # Query with in
    resp = await cli.get("/torrent?spritzle.tags.in=linux,ubuntu")
    assert resp.status == 200
    assert (await resp.json()) == [info_hash]

    # Query with all
    resp = await cli.get("/torrent?spritzle.tags.all=linux,iso")
    assert resp.status == 200
    assert (await resp.json()) == [info_hash]

    resp = await cli.get("/torrent?spritzle.tags.all=linux,windows")
    assert resp.status == 200
    assert (await resp.json()) == []


async def test_get_torrent_query_with_heterogeneous_tags(cli):
    from spritzle.daemon.keys import APP_KEY_CORE
    core = cli.app[APP_KEY_CORE]

    # Add torrent 1 and simulate it lacking spritzle.tags (e.g. ghost torrent / external resume)
    p1 = create_torrent_post_data(filename="testtorrent1.torrent")
    resp1 = await cli.post("/torrent", json=p1)
    assert resp1.status == 201
    info_hash1 = (await resp1.json())["info_hash"]
    core.torrent_data[info_hash1] = {}  # No spritzle.tags

    # Add torrent 2 WITH tags
    p2 = create_torrent_post_data(
        filename="random_one_file.torrent", tags=["linux", "iso"]
    )
    resp2 = await cli.post("/torrent", json=p2)
    assert resp2.status == 201
    info_hash2 = (await resp2.json())["info_hash"]

    # Querying should succeed and only return torrent 2, NOT raise 400
    resp = await cli.get("/torrent?spritzle.tags=linux")
    assert resp.status == 200
    assert (await resp.json()) == [info_hash2]


@pytest.mark.parametrize(
    "query,want",
    [
        ({"string": ".*oo.*"}, ["t2", "t3"]),
        ({"string": ".*oo.*", "int.ge": "10"}, ["t2"]),
        ({"float.gt": "500.0", "int.lt": "0"}, ["t3"]),
        ({"int.ge": "400"}, []),
        ({"string": ".*r.*", "bool": "true"}, ["t1", "t3"]),
        ({"int": "10"}, ["t2"]),
        ({"spritzle.int.gt": "10"}, ["t1"]),
        ({"spritzle.int": "100"}, ["t1"]),
        ({"string.ne": ".*oo.*"}, ["t1"]),
        ({"string.eq": "foobar"}, ["t2"]),
        ({"bool.ne": "true"}, ["t2"]),
        ({"bool.eq": "true"}, ["t1", "t3"]),
        ({"bool.ne": "false"}, ["t1", "t3"]),
    ],
)
def test_get_torrent_list_by_query(query, want):
    statuses = [
        {
            "info_hash": "t1",
            "string": "stringvalue",
            "int": 100,
            "float": 50.0,
            "bool": True,
            "spritzle.int": 100,
        },
        {
            "info_hash": "t2",
            "string": "foobar",
            "int": 10,
            "float": 500.0,
            "bool": False,
            "spritzle.int": 10,
        },
        {
            "info_hash": "t3",
            "string": "raboof",
            "int": -1,
            "float": 5000.0,
            "bool": True,
            "spritzle.int": -1,
        },
    ]
    torrents = torrent.get_torrent_list_by_query(query, statuses)
    assert torrents == want


async def test_post_torrent(cli):
    post_data = create_torrent_post_data(
        filename="random_one_file.torrent", tags=["foo"]
    )
    response = await cli.post("/torrent", json=post_data)
    body = await response.json()
    assert "info_hash" in body
    info_hash = body["info_hash"]

    assert (
        response.headers["LOCATION"]
        == f"http://{cli.host}:{cli.port}/torrent/{info_hash}"
    )
    assert response.status == 201

    assert info_hash == "44a040be6d74d8d290cd20128788864cbf770719"

    response = await cli.get("/torrent")
    tlist = await response.json()
    assert tlist == ["44a040be6d74d8d290cd20128788864cbf770719"]
    return info_hash


async def test_post_torrent_info_hash(cli):
    post_data = create_torrent_post_data(
        info_hash="44a040be6d74d8d290cd20128788864cbf770719"
    )

    response = await cli.post("/torrent", json=post_data)
    body = await response.json()
    assert "info_hash" in body
    info_hash = body["info_hash"]
    assert info_hash == "44a040be6d74d8d290cd20128788864cbf770719"


async def test_add_torrent_lt_runtime_error(cli, core):
    post_data = create_torrent_post_data(filename="random_one_file.torrent")

    add_torrent = MagicMock()
    add_torrent.side_effect = RuntimeError()
    core.session.add_torrent = add_torrent
    response = await cli.post("/torrent", json=post_data)
    assert response.status == 500


async def test_add_torrent_bad_file(cli):
    post_data = create_torrent_post_data(filename="empty.torrent")

    response = await cli.post("/torrent", json=post_data)
    assert response.status == 400


async def test_add_torrent_bad_number_args(cli):
    post_data = create_torrent_post_data(
        url="http://testing/test.torrent", info_hash="a0" * 20
    )

    response = await cli.post("/torrent", json=post_data)
    assert response.status == 400


async def test_add_torrent_bad_args(cli):
    post_data = create_torrent_post_data(
        filename="random_one_file.torrent", args={"bad_key": True}
    )

    response = await cli.post("/torrent", json=post_data)
    assert response.status == 400


async def test_add_torrent_url(cli):
    torrent_address = str(cli.make_url("/test_torrents/random_one_file.torrent"))

    post_data = create_torrent_post_data(url=torrent_address)

    response = await cli.post("/torrent", json=post_data)
    assert response.status == 201


async def test_add_torrent_url_invalid_scheme(cli):
    post_data = create_torrent_post_data(url="file:///etc/passwd")
    response = await cli.post("/torrent", json=post_data)
    assert response.status == 400


async def test_add_torrent_url_metadata_blocked(cli):
    post_data = create_torrent_post_data(url="http://169.254.169.254/latest/meta-data")
    response = await cli.post("/torrent", json=post_data)
    assert response.status == 400



async def test_remove_torrent(cli):
    tid = await test_post_torrent(cli)

    response = await cli.delete(f"/torrent/{tid}", params={"delete_files": 1})
    assert response.status == 200

    response = await cli.get("/torrent")
    torrents = await response.json()
    assert response.status == 200
    assert len(torrents) == 0


async def test_delete_torrent_delete_files_boolean_handling(cli, core):
    from unittest.mock import patch

    for false_val in ("false", "0", "no", "off", "FALSE"):
        tid = await test_post_torrent(cli)
        with patch.object(core.torrent, "remove", wraps=core.torrent.remove) as mock_remove:
            response = await cli.delete(f"/torrent/{tid}", params={"delete_files": false_val})
            assert response.status == 200
            assert mock_remove.called
            args, _ = mock_remove.call_args
            options = args[1]
            assert not bool(options & lt.options_t.delete_files), (
                f"Expected delete_files to be False for {false_val}, got options={options}"
            )

    for true_val in ("true", "1", "yes", "on", ""):
        tid = await test_post_torrent(cli)
        with patch.object(core.torrent, "remove", wraps=core.torrent.remove) as mock_remove:
            response = await cli.delete(f"/torrent/{tid}", params={"delete_files": true_val})
            assert response.status == 200
            assert mock_remove.called
            args, _ = mock_remove.call_args
            options = args[1]
            assert bool(options & lt.options_t.delete_files), (
                f"Expected delete_files to be True for {true_val}, got options={options}"
            )


async def test_remove_torrent_all(cli, core):
    await test_post_torrent(cli)

    response = await cli.delete("/torrent", params={"delete_files": 1})
    assert response.status == 200
    assert len(torrent.get_torrent_list(core)) == 0


async def test_remove_torrent_missing_from_torrent_data(cli, core):
    tid = await test_post_torrent(cli)
    # Remove from torrent_data to simulate ghost / missing metadata
    core.torrent_data.pop(tid, None)

    response = await cli.delete(f"/torrent/{tid}")
    assert response.status == 200
    assert tid not in core.torrent_data
    assert len(torrent.get_torrent_list(core)) == 0


async def test_get_torrent_invalid_hex(cli):
    response = await cli.get("/torrent/not-a-valid-hex")
    assert response.status in (400, 404)


async def test_delete_torrent_not_found(cli):
    nonexistent_tid = "a" * 40
    response = await cli.delete(f"/torrent/{nonexistent_tid}")
    assert response.status == 404


async def test_delete_torrent_invalid_hex(cli):
    response = await cli.delete("/torrent/not-a-valid-hex")
    assert response.status == 400


async def test_delete_torrent_timeout(cli, monkeypatch):
    tid = await test_post_torrent(cli)

    async def mock_remove(*args, **kwargs):
        raise asyncio.TimeoutError()

    from spritzle.daemon.keys import APP_KEY_CORE

    core = cli.app[APP_KEY_CORE]
    monkeypatch.setattr(core.torrent, "remove", mock_remove)

    response = await cli.delete(f"/torrent/{tid}")
    assert response.status == 504


async def test_delete_torrent_alert_exception_handling(cli, monkeypatch):
    tid = await test_post_torrent(cli)
    from spritzle.daemon.keys import APP_KEY_CORE
    from spritzle.daemon.torrent import AlertException
    from unittest.mock import Mock

    core = cli.app[APP_KEY_CORE]

    async def mock_remove(handle, *args, **kwargs):
        # In libtorrent, remove_torrent is invoked and handle becomes invalid
        # by the time torrent_delete_failed_alert is dispatched.
        core.session.remove_torrent(handle)
        for _ in range(10):
            core.session.wait_for_alert(100)
            core.session.pop_alerts()
        assert not handle.is_valid()
        raise AlertException(Mock(message=lambda: "Failed to delete files"))

    monkeypatch.setattr(core.torrent, "remove", mock_remove)

    response = await cli.delete(f"/torrent/{tid}", params={"delete_files": 1})
    assert response.status == 200
    assert tid not in core.torrent_data





async def test_pause_resume_torrent(cli):
    tid = await test_post_torrent(cli)

    response = await cli.get(f"/torrent/{tid}")
    data = await response.json()
    assert data["flags"] & lt.torrent_flags.paused

    await cli.post(f"/torrent/{tid}/resume")
    response = await cli.get(f"/torrent/{tid}")
    data = await response.json()
    assert not data["flags"] & lt.torrent_flags.paused

    await cli.post(f"/torrent/{tid}/pause")
    response = await cli.get(f"/torrent/{tid}")
    data = await response.json()
    assert data["flags"] & lt.torrent_flags.paused


async def test_edit_queue_position(cli):
    t1_url = str(cli.make_url("/test_torrents/testtorrent1.torrent"))
    t2_url = str(cli.make_url("/test_torrents/testtorrent2.torrent"))
    t3_url = str(cli.make_url("/test_torrents/testtorrent3.torrent"))
    r = await cli.post("/torrent", json={"url": t1_url})
    t1_id = (await r.json())["info_hash"]
    r = await cli.post("/torrent", json={"url": t2_url})
    t2_id = (await r.json())["info_hash"]
    r = await cli.post("/torrent", json={"url": t3_url})
    t3_id = (await r.json())["info_hash"]

    # Verify initial state
    r = await cli.get(f"/torrent/{t1_id}")
    status = await r.json()
    assert status["queue_position"] == 0
    r = await cli.get(f"/torrent/{t2_id}")
    status = await r.json()
    assert status["queue_position"] == 1
    r = await cli.get(f"/torrent/{t3_id}")
    status = await r.json()
    assert status["queue_position"] == 2

    # Test queue movement actions
    await cli.post(f"/torrent/{t1_id}/queue_position_down")
    r = await cli.get(f"/torrent/{t1_id}")
    status = await r.json()
    assert status["queue_position"] == 1

    await cli.post(f"/torrent/{t1_id}/queue_position_up")
    r = await cli.get(f"/torrent/{t1_id}")
    status = await r.json()
    assert status["queue_position"] == 0

    await cli.post(f"/torrent/{t1_id}/queue_position_bottom")
    r = await cli.get(f"/torrent/{t1_id}")
    status = await r.json()
    assert status["queue_position"] == 2

    await cli.post(f"/torrent/{t1_id}/queue_position_top")
    r = await cli.get(f"/torrent/{t1_id}")
    status = await r.json()
    assert status["queue_position"] == 0


async def test_torrent_flags(cli):
    tid = await test_post_torrent(cli)

    r = await cli.get(f"/torrent/{tid}/flags")
    flags = await r.json()
    assert not flags["auto_managed"]
    assert not flags["seed_mode"]

    r = await cli.get(f"/torrent/{tid}/flags/auto_managed")
    value = await r.json()
    assert not value

    await cli.put(f"/torrent/{tid}/flags/auto_managed", json=True)
    r = await cli.get(f"/torrent/{tid}/flags")
    flags = await r.json()
    assert flags["auto_managed"]

    r = await cli.get(f"/torrent/{tid}/flags/auto_managed")
    value = await r.json()
    assert value

    await cli.put(
        f"/torrent/{tid}/flags", json={"auto_managed": False, "super_seeding": True}
    )
    r = await cli.get(f"/torrent/{tid}/flags")
    flags = await r.json()
    assert not flags["auto_managed"]
    assert flags["super_seeding"]

    r = await cli.put(f"/torrent/{tid}/flags", json={"bad_flag": True})
    assert r.status == 400


async def test_force_recheck(cli):
    tid = await test_post_torrent(cli)

    r = await cli.get(f"/torrent/{tid}")
    status = await r.json()
    assert status["state"] != "checking_resume_data"
    await cli.post(f"/torrent/{tid}/pause")
    r = await cli.get(f"/torrent/{tid}")
    status = await r.json()
    assert status["flags"] & lt.torrent_flags.paused

    await cli.put(f"/torrent/{tid}/flags/auto_managed", json=True)
    r = await cli.put("/session/settings", json={"active_checking": 0})
    assert r.status == 200

    r = await cli.post(f"/torrent/{tid}/force_recheck")
    assert r.status == 200

    r = await cli.get(f"/torrent/{tid}")
    status = await r.json()
    assert status["state"] in ("checking_resume_data", "downloading")



async def test_set_max_uploads(cli):
    tid = await test_post_torrent(cli)

    await cli.post(f"/torrent/{tid}/set_max_uploads", json=[10])
    r = await cli.get(f"/torrent/{tid}")
    status = await r.json()
    assert status["uploads_limit"] == 10

    await cli.post(f"/torrent/{tid}/set_max_uploads", json=[255])
    r = await cli.get(f"/torrent/{tid}")
    status = await r.json()
    assert status["uploads_limit"] == 255


async def test_disallowed_torrent_method(cli):
    tid = await test_post_torrent(cli)
    r = await cli.post(f"/torrent/{tid}/move_storage", json=["/tmp"])
    assert r.status == 400


async def test_post_torrent_non_dict_body(cli):
    r = await cli.post("/torrent", json=[])
    assert r.status == 400


async def test_put_flags_invalid_json(cli):
    tid = await test_post_torrent(cli)
    r = await cli.put(
        f"/torrent/{tid}/flags",
        data="not a json string",
        headers={"Content-Type": "application/json"},
    )
    assert r.status == 400


async def test_put_flags_non_dict_body(cli):
    tid = await test_post_torrent(cli)
    r = await cli.put(f"/torrent/{tid}/flags", json=[])
    assert r.status == 400


async def test_post_torrent_invalid_file_base64(cli):
    r = await cli.post("/torrent", json={"file": "not_valid_base64!!!"})
    assert r.status == 400


async def test_post_torrent_invalid_info_hash_format(cli):
    r = await cli.post("/torrent", json={"info_hash": "not_valid_hex"})
    assert r.status == 400


async def test_post_torrent_invalid_info_hash_length(cli):
    r = await cli.post("/torrent", json={"info_hash": "abcd"})
    assert r.status == 400


async def test_get_torrent_invalid_flag(cli):
    tid = await test_post_torrent(cli)
    r = await cli.get(f"/torrent/{tid}/flags/not_a_valid_flag")
    assert r.status in (400, 404)


def test_get_torrent_list_by_query_unhandled_or_none_type():
    from spritzle.daemon.resource.torrent import get_torrent_list_by_query
    statuses = [
        {"info_hash": "hash1", "error": {"code": 1, "msg": "err"}, "custom_none": None},
        {"info_hash": "hash2", "error": None, "custom_none": None},
    ]
    # Querying equality for unhandled type/None must NOT match
    res = get_torrent_list_by_query({"error": "err"}, statuses)
    assert res == []

    # Querying .ne should match
    res_ne = get_torrent_list_by_query({"error.ne": "err"}, statuses)
    assert res_ne == ["hash1", "hash2"]


async def test_delete_torrent_bulk_with_query_filter(cli):
    p1 = create_torrent_post_data(filename="testtorrent1.torrent", tags=["tag_delete"])
    resp1 = await cli.post("/torrent", json=p1)
    assert resp1.status == 201
    h1 = (await resp1.json())["info_hash"]

    p2 = create_torrent_post_data(filename="random_one_file.torrent", tags=["tag_keep"])
    resp2 = await cli.post("/torrent", json=p2)
    assert resp2.status == 201
    h2 = (await resp2.json())["info_hash"]

    # Delete with query filter
    del_resp = await cli.delete("/torrent?spritzle.tags=tag_delete")
    assert del_resp.status == 200

    # h1 should be deleted, h2 should still exist
    list_resp = await cli.get("/torrent")
    remaining = await list_resp.json()
    assert h1 not in remaining
    assert h2 in remaining


async def test_post_torrent_failure_does_not_leak_metadata(cli, monkeypatch):
    from spritzle.daemon.keys import APP_KEY_CORE
    core = cli.app[APP_KEY_CORE]

    def mock_add_torrent(*args, **kwargs):
        raise RuntimeError("Libtorrent disk error")

    monkeypatch.setattr(core.session, "add_torrent", mock_add_torrent)
    p = create_torrent_post_data(filename="testtorrent1.torrent", tags=["will_fail"])
    resp = await cli.post("/torrent", json=p)
    assert resp.status == 500

    # Metadata must not have leaked into core.torrent_data
    for h, data in core.torrent_data.items():
        assert "will_fail" not in data.get("spritzle.tags", [])


def test_get_torrent_list_by_query_invalid_operators():
    from aiohttp import web
    statuses = [{"info_hash": "t1", "string": "foo", "bool": True}]

    with pytest.raises(web.HTTPBadRequest, match="Invalid operator gt"):
        torrent.get_torrent_list_by_query({"string.gt": "bar"}, statuses)

    with pytest.raises(web.HTTPBadRequest, match="Invalid operator lt"):
        torrent.get_torrent_list_by_query({"bool.lt": "true"}, statuses)


async def test_post_torrent_tags_validation(cli):
    # String instead of list
    p1 = create_torrent_post_data(filename="testtorrent1.torrent")
    p1["spritzle.tags"] = "invalid_string_tag"
    r1 = await cli.post("/torrent", json=p1)
    assert r1.status == 400

    # Non-string elements in list
    p2 = create_torrent_post_data(filename="testtorrent1.torrent")
    p2["spritzle.tags"] = [1, 2]
    r2 = await cli.post("/torrent", json=p2)
    assert r2.status == 400

    # null tags should be normalized to []
    p3 = create_torrent_post_data(filename="testtorrent1.torrent")
    p3["spritzle.tags"] = None
    r3 = await cli.post("/torrent", json=p3)
    assert r3.status == 201
    h3 = (await r3.json())["info_hash"]
    from spritzle.daemon.keys import APP_KEY_CORE
    core = cli.app[APP_KEY_CORE]
    assert core.torrent_data[h3]["spritzle.tags"] == []







