#
# tests/cli/test_shell_completion.py
#
# Copyright (C) 2026 Andrew Resch <andrewresch@gmail.com>
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

from click.shell_completion import BashComplete
from click.testing import CliRunner

from spritzle.cli.completion_helpers import (
    TORRENT_FLAGS,
    complete_remotes,
    complete_torrent_flags,
    complete_torrent_identifiers,
)
from spritzle.cli.config import RemotesConfig
from spritzle.cli.main import cli as spritzle_cli


def test_complete_torrent_flags():
    all_flags = complete_torrent_flags(None, None, "")
    assert len(all_flags) == len(TORRENT_FLAGS)
    values = [item.value for item in all_flags]
    assert "sequential_download" in values
    assert "seed_mode" in values

    seq_flags = complete_torrent_flags(None, None, "seq")
    assert [item.value for item in seq_flags] == ["sequential_download"]

    none_flags = complete_torrent_flags(None, None, "nonexistent_flag_xyz")
    assert none_flags == []


def test_complete_remotes(tmp_path):
    remotes_cfg = RemotesConfig(config_dir=tmp_path)
    remotes_cfg.set_remote("box-alpha", "http://10.0.0.1:17382", "d1", "k1")
    remotes_cfg.set_remote("box-beta", "http://10.0.0.2:17382", "d2", "k2")

    # Create dummy Click context with --config set
    ctx = spritzle_cli.make_context("spritzle", ["-c", str(tmp_path)])

    items = complete_remotes(ctx, None, "")
    names = [i.value for i in items]
    assert "box-alpha" in names
    assert "box-beta" in names

    filtered = complete_remotes(ctx, None, "box-a")
    assert [i.value for i in filtered] == ["box-alpha"]

    # Graceful handling when no remotes or error
    empty_items = complete_remotes(None, None, "xyz")
    assert isinstance(empty_items, list)


def test_complete_torrent_identifiers_offline(tmp_path):
    # When remote daemon is offline/unreachable, completion must not raise and return []
    remotes_cfg = RemotesConfig(config_dir=tmp_path)
    remotes_cfg.set_remote("offline", "http://127.0.0.1:59999", "dummy_id", "dummy_key")
    ctx = spritzle_cli.make_context("spritzle", ["-c", str(tmp_path), "-r", "offline"])
    items = complete_torrent_identifiers(ctx, None, "")
    assert items == []


def test_complete_torrent_identifiers_online(monkeypatch, tmp_path):
    class MockResponse:
        status = 200

        async def json(self):
            return [
                {"info_hash": "a" * 40, "name": "archlinux-2026.iso"},
                {"info_hash": "b" * 40, "name": "other-torrent"},
            ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class MockSession:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return MockResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    import aiohttp

    monkeypatch.setattr(aiohttp, "ClientSession", MockSession)

    remotes_cfg = RemotesConfig(config_dir=tmp_path)
    remotes_cfg.set_remote("mock", "http://127.0.0.1:17382", "id", "key")
    ctx = spritzle_cli.make_context("spritzle", ["-c", str(tmp_path), "-r", "mock"])

    # Empty prefix -> returns all info-hashes
    all_items = complete_torrent_identifiers(ctx, None, "")
    assert len(all_items) == 2
    assert all_items[0].value == "a" * 40
    assert all_items[0].help == "archlinux-2026.iso"

    # Hash prefix matching
    a_items = complete_torrent_identifiers(ctx, None, "aaa")
    assert len(a_items) == 1
    assert a_items[0].value == "a" * 40

    # Name prefix matching
    arch_items = complete_torrent_identifiers(ctx, None, "arch")
    assert len(arch_items) == 1
    assert arch_items[0].value == "archlinux-2026.iso"


def test_click_root_completions():
    comp = BashComplete(spritzle_cli, {}, "spritzle", "_SPRITZLE_COMPLETE")
    items = comp.get_completions([], "")
    values = [i.value for i in items]
    for expected in [
        "add",
        "completion",
        "config",
        "daemon-config",
        "flags",
        "help",
        "info",
        "list",
        "move-storage",
        "pause",
        "remote",
        "remove",
        "resume",
        "settings",
        "stats",
        "status",
        "top",
    ]:
        assert expected in values


def test_click_flags_completion():
    comp = BashComplete(spritzle_cli, {}, "spritzle", "_SPRITZLE_COMPLETE")
    items = comp.get_completions(["flags", "-s"], "seq")
    assert [i.value for i in items] == ["sequential_download"]

    items_u = comp.get_completions(["flags", "-u"], "seed")
    assert [i.value for i in items_u] == ["seed_mode"]


def test_click_remote_completions(tmp_path):
    remotes_cfg = RemotesConfig(config_dir=tmp_path)
    remotes_cfg.set_remote("prod-server", "https://prod.example.com", "dp", "kp")

    comp = BashComplete(spritzle_cli, {}, "spritzle", "_SPRITZLE_COMPLETE")
    subcmds = [i.value for i in comp.get_completions(["remote"], "")]
    assert "use" in subcmds
    assert "remove" in subcmds
    assert "status" in subcmds

    # Autocomplete remote names on 'remote use'
    use_items = comp.get_completions(["-c", str(tmp_path), "remote", "use"], "")
    assert "prod-server" in [i.value for i in use_items]

    # Autocomplete remote names on top-level -r / --remote
    r_items = comp.get_completions(["-c", str(tmp_path), "-r"], "")
    assert "prod-server" in [i.value for i in r_items]


def test_click_path_completions():
    comp = BashComplete(spritzle_cli, {}, "spritzle", "_SPRITZLE_COMPLETE")

    # spritzle add expects a path/file
    add_items = comp.get_completions(["add"], "")
    assert any(i.type == "file" for i in add_items)

    # spritzle move-storage <ih> expects a destination directory
    move_storage_items = comp.get_completions(["move-storage", "dummy_hash"], "")
    assert any(i.type == "dir" for i in move_storage_items)


def test_spritzle_completion_command():
    runner = CliRunner()

    for shell, marker in [
        ("bash", "_spritzle_completion"),
        ("zsh", "compdef _spritzle_completion spritzle"),
        ("fish", "--command spritzle"),
    ]:
        res = runner.invoke(spritzle_cli, ["completion", shell])
        assert res.exit_code == 0
        assert marker in res.output

    # Unsupported shell returns error
    res_err = runner.invoke(spritzle_cli, ["completion", "powershell"])
    assert res_err.exit_code != 0


def test_complete_profiles():
    from spritzle.cli.completion_helpers import PROFILES, complete_profiles

    items = complete_profiles(None, None, "")
    assert len(items) == len(PROFILES)
    values = [i.value for i in items]
    assert "deluge-2.1.1" in values

    deluge_items = complete_profiles(None, None, "del")
    assert [i.value for i in deluge_items] == ["deluge-2.1.1"]


def test_complete_torrent_identifiers_extra_branches(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch
    from spritzle.cli.completion_helpers import complete_torrent_identifiers

    # 1. ctx.obj present with empty base_url/token
    mock_ctx = MagicMock()
    mock_client = MagicMock()
    mock_client.base_url = ""
    mock_client.token = ""
    mock_ctx.obj = mock_client
    assert complete_torrent_identifiers(mock_ctx, None, "") == []

    # 2. Client TLS settings and non-dict items
    mock_client.base_url = "http://127.0.0.1:8080"
    mock_client.token = "test"
    mock_client.insecure = True
    mock_client.fingerprint = "aa:bb"
    mock_client.ca_cert = "/dev/null"
    mock_client.url = lambda *args: "http://127.0.0.1:8080/torrent"

    class MockResp:
        status = 200
        async def json(self):
            return ["0123456789abcdef0123456789abcdef01234567"]
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    class MockSession:
        def __init__(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            return MockResp()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    import aiohttp
    monkeypatch.setattr(aiohttp, "ClientSession", MockSession)

    items = complete_torrent_identifiers(mock_ctx, None, "")
    assert len(items) == 1
    assert items[0].value == "0123456789abcdef0123456789abcdef01234567"

    # With fingerprint
    mock_client.insecure = False
    mock_client.fingerprint = "00" * 32
    assert len(complete_torrent_identifiers(mock_ctx, None, "")) == 1

    # With ca_cert
    mock_client.fingerprint = None
    import ssl
    real_ctx = ssl.create_default_context()
    with patch("ssl.create_default_context", return_value=real_ctx):
        assert len(complete_torrent_identifiers(mock_ctx, None, "")) == 1
