#
# test_remote.py
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

import json
from click.testing import CliRunner
import pytest

from spritzle.daemon.resource.auth import auth_middleware
from spritzle.cli.main import cli as spritzle_cli


@pytest.fixture
def cli(loop, core, app, aiohttp_client):
    app.middlewares.append(auth_middleware)
    return loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"host": "127.0.0.1", "port": 0})
    )



def test_remote_add_and_list(cli, core, tmp_path):
    runner = CliRunner()
    raw_key, _ = core.key_manager.create_key(name="laptop")
    daemon_url = f"http://127.0.0.1:{cli.server.port}"

    # Add remote
    res = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "add", "seedbox", daemon_url, "--key", raw_key],
    )
    assert res.exit_code == 0
    assert "Added remote 'seedbox'" in res.output
    assert core.identity.daemon_id in res.output

    # List remotes (plain)
    res_list = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "list", "--plain"],
    )
    assert res_list.exit_code == 0
    assert "seedbox" in res_list.output
    assert core.identity.daemon_id in res_list.output

    # List remotes (rich / interactive)
    res_rich = runner.invoke(
        spritzle_cli,
        ["--color", "-c", str(tmp_path), "remote", "list"],
    )
    assert res_rich.exit_code == 0
    assert "╭" in res_rich.output
    assert "seedbox" in res_rich.output
    assert "* default remote" in res_rich.output

    # List remotes (json)
    res_json = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "list", "--json"],
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert any(r["name"] == "seedbox" and r["is_default"] is True for r in data)


def test_remote_show_and_set_key(cli, core, tmp_path):
    runner = CliRunner()
    raw_key1, _ = core.key_manager.create_key(name="k1")
    daemon_url = f"http://127.0.0.1:{cli.server.port}"

    runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "add", "box", daemon_url, "--key", raw_key1],
    )

    # Show remote (json)
    res_show = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "show", "box", "--json"],
    )
    assert res_show.exit_code == 0
    info = json.loads(res_show.output)
    assert info["name"] == "box"
    assert info["daemon_id"] == core.identity.daemon_id

    # Show remote (rich / interactive)
    res_show_rich = runner.invoke(
        spritzle_cli,
        ["--color", "-c", str(tmp_path), "remote", "show", "box"],
    )
    assert res_show_rich.exit_code == 0
    assert "╭" in res_show_rich.output
    assert "Remote: box" in res_show_rich.output
    assert "Property" in res_show_rich.output

    # Update key
    raw_key2, _ = core.key_manager.create_key(name="k2")
    res_set = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "set-key", "box", raw_key2],
    )
    assert res_set.exit_code == 0
    assert "Updated API key for remote 'box'" in res_set.output


def test_remote_use_and_remove(cli, core, tmp_path):
    runner = CliRunner()
    raw_key, _ = core.key_manager.create_key(name="test")
    daemon_url = f"http://127.0.0.1:{cli.server.port}"

    runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "add", "r1", daemon_url, "--key", raw_key],
    )
    runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "add", "r2", daemon_url, "--key", raw_key],
    )

    # Switch remote
    res_use = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "use", "r2"],
    )
    assert res_use.exit_code == 0
    assert "Switched default remote to 'r2'" in res_use.output

    # Remove remote
    res_rm = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "remove", "r1"],
    )
    assert res_rm.exit_code == 0
    assert "Removed remote 'r1'" in res_rm.output


def test_remote_identity_mismatch_protection(cli, core, tmp_path):
    from spritzle.cli.config import RemotesConfig

    raw_key, _ = core.key_manager.create_key(name="test")
    cfg = RemotesConfig(config_dir=tmp_path)
    # Configure remote with an intentionally wrong daemon_id
    cfg.set_remote("fakebox", f"http://127.0.0.1:{cli.server.port}", "spz_d_wrong_fingerprint", raw_key)
    cfg.set_default_remote("fakebox")

    runner = CliRunner()
    res = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "list"],
    )
    assert res.exit_code == 1
    assert "Daemon identity mismatch" in res.output


def test_remote_status(cli, core, tmp_path):
    from spritzle.cli.config import RemotesConfig

    runner = CliRunner()
    raw_key, _ = core.key_manager.create_key(name="laptop")
    daemon_url = f"http://127.0.0.1:{cli.server.port}"

    runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "add", "box", daemon_url, "--key", raw_key],
    )

    # Check status of all remotes (rich / default)
    res_all = runner.invoke(
        spritzle_cli,
        ["--color", "-c", str(tmp_path), "remote", "status"],
    )
    assert res_all.exit_code == 0
    assert "╭" in res_all.output
    assert "box" in res_all.output
    assert "online" in res_all.output
    assert "* default remote" in res_all.output

    # Check status of all remotes (plain)
    res_plain = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "status", "--plain"],
    )
    assert res_plain.exit_code == 0
    assert "box" in res_plain.output
    assert "online" in res_plain.output

    # Check status of all remotes (json)
    res_json = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "status", "--json"],
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "box"
    assert data[0]["status"] == "online"
    assert data[0]["num_torrents"] == 0
    assert data[0]["daemon_id"] == core.identity.daemon_id
    assert data[0]["uptime"] is not None

    # Check single remote (json)
    res_single_json = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "status", "box", "--json"],
    )
    assert res_single_json.exit_code == 0
    single_data = json.loads(res_single_json.output)
    assert isinstance(single_data, dict)
    assert single_data["name"] == "box"
    assert single_data["status"] == "online"

    # Non-existent remote
    res_missing = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "status", "nonexistent"],
    )
    assert res_missing.exit_code == 1
    assert "Remote 'nonexistent' does not exist." in res_missing.output

    # Unreachable remote
    cfg = RemotesConfig(config_dir=tmp_path)
    cfg.set_remote("deadbox", "http://127.0.0.1:1", "spz_d_dead", "spritzle_dummy")
    res_dead = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "status", "deadbox", "--json"],
    )
    assert res_dead.exit_code == 0
    dead_data = json.loads(res_dead.output)
    assert dead_data["name"] == "deadbox"
    assert dead_data["status"] == "offline"

