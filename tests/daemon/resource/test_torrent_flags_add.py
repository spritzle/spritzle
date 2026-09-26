from base64 import b64encode
from pathlib import Path

import libtorrent as lt
import pytest

from spritzle.daemon.resource.torrent import parse_add_torrent_flags
from ..common import torrent_dir


def test_parse_add_torrent_flags_unit():
    # Int
    assert parse_add_torrent_flags(16) == 16
    assert parse_add_torrent_flags("16") == 16

    # List of strings
    paused_flag = int(lt.torrent_flags.paused)
    auto_flag = int(lt.torrent_flags.auto_managed)
    assert parse_add_torrent_flags(["paused"]) == paused_flag
    assert parse_add_torrent_flags(["paused", "auto_managed"]) == (paused_flag | auto_flag)

    # Comma-separated string
    assert parse_add_torrent_flags("paused,auto_managed") == (paused_flag | auto_flag)

    # Dict
    assert parse_add_torrent_flags({"paused": True, "auto_managed": False}, default_flags=auto_flag) == paused_flag
    assert parse_add_torrent_flags({"paused": "yes", "auto_managed": "0"}, default_flags=auto_flag) == paused_flag

    # Invalid flag
    with pytest.raises(Exception):
        parse_add_torrent_flags(["nonexistent_flag"])

    with pytest.raises(Exception):
        parse_add_torrent_flags("nonexistent_flag")

    with pytest.raises(Exception):
        parse_add_torrent_flags({"nonexistent_flag": True})

    with pytest.raises(Exception):
        parse_add_torrent_flags(True)

    with pytest.raises(Exception):
        parse_add_torrent_flags([123])


async def test_post_torrent_with_flag_list(cli):
    filepath = Path(torrent_dir, "random_one_file.torrent")
    file_b64 = b64encode(filepath.open(mode="rb").read()).decode("ascii")

    # Add paused via flag list
    post_data = {
        "file": file_b64,
        "flags": ["paused"],
    }
    response = await cli.post("/torrent", json=post_data)
    assert response.status == 201
    body = await response.json()
    info_hash = body["info_hash"]

    # Verify torrent is paused
    status_resp = await cli.get(f"/torrent/{info_hash}")
    assert status_resp.status == 200
    st = await status_resp.json()
    assert st["paused"] is True


async def test_post_torrent_with_invalid_flags(cli):
    filepath = Path(torrent_dir, "random_one_file.torrent")
    file_b64 = b64encode(filepath.open(mode="rb").read()).decode("ascii")

    post_data = {
        "file": file_b64,
        "flags": ["totally_fake_flag"],
    }
    response = await cli.post("/torrent", json=post_data)
    assert response.status == 400


async def test_post_torrent_magnet_with_flags(cli):
    magnet = "magnet:?xt=urn:btih:0123456789012345678901234567890123456789&dn=test_flags"
    post_data = {
        "url": magnet,
        "flags": ["paused"],
    }
    response = await cli.post("/torrent", json=post_data)
    assert response.status == 201
    body = await response.json()
    info_hash = body["info_hash"]

    status_resp = await cli.get(f"/torrent/{info_hash}")
    assert status_resp.status == 200
    st = await status_resp.json()
    assert st["paused"] is True
