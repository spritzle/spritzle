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
from spritzle.cli.display import strip_ansi
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
    assert "* default remote" in strip_ansi(res_rich.output)

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
    assert "* default remote" in strip_ansi(res_all.output)

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


def test_remote_add_tls_flags(cli, core, tmp_path):
    from spritzle.cli.config import RemotesConfig

    runner = CliRunner()
    raw_key, _ = core.key_manager.create_key(name="laptop")
    daemon_url = f"http://127.0.0.1:{cli.server.port}"
    ca_file = tmp_path / "ca.crt"
    ca_file.write_text("dummy ca")

    res = runner.invoke(
        spritzle_cli,
        [
            "-c",
            str(tmp_path),
            "remote",
            "add",
            "tlsbox",
            daemon_url,
            "--key",
            raw_key,
            "--insecure",
            "--ca-cert",
            str(ca_file),
            "--fingerprint",
            "aa:bb:cc:dd",
        ],
    )
    assert res.exit_code == 0, res.output
    cfg = RemotesConfig(config_dir=tmp_path)
    remote = cfg.get_remote("tlsbox")
    assert remote is not None
    assert remote["insecure"] is True
    assert remote["ca_cert"] == str(ca_file)
    assert remote["fingerprint"] == "aa:bb:cc:dd"


def test_remote_set_key_preserves_tls_flags(cli, core, tmp_path):
    from spritzle.cli.config import RemotesConfig

    runner = CliRunner()
    raw_key, _ = core.key_manager.create_key(name="laptop")
    daemon_url = f"http://127.0.0.1:{cli.server.port}"
    ca_file = tmp_path / "ca.crt"
    ca_file.write_text("dummy ca")

    cfg = RemotesConfig(config_dir=tmp_path)
    cfg.set_remote(
        "tlsbox",
        daemon_url,
        core.identity.daemon_id,
        raw_key,
        insecure=True,
        ca_cert=str(ca_file),
        fingerprint="aa:bb:cc:dd",
    )

    new_key, _ = core.key_manager.create_key(name="new_key")
    res = runner.invoke(
        spritzle_cli,
        [
            "-c",
            str(tmp_path),
            "remote",
            "set-key",
            "tlsbox",
            new_key,
        ],
    )
    assert res.exit_code == 0, res.output
    cfg.load()
    updated_remote = cfg.get_remote("tlsbox")
    assert updated_remote is not None
    assert updated_remote["key"] == new_key
    assert updated_remote["insecure"] is True
    assert updated_remote["ca_cert"] == str(ca_file)
    assert updated_remote["fingerprint"] == "aa:bb:cc:dd"


def test_format_uptime_and_normalize_url():
    import click
    from spritzle.cli.commands.remote import format_uptime, normalize_url

    assert format_uptime(45) == "45s"
    assert format_uptime(125) == "2m 5s"
    assert format_uptime(3665) == "1h 1m"
    assert format_uptime(90000) == "1d 1h"

    assert normalize_url("127.0.0.1:8080") == "http://127.0.0.1:8080"
    assert normalize_url("http://localhost:8080/") == "http://localhost:8080"
    assert normalize_url("https://remote.example.com") == "https://remote.example.com"

    with pytest.raises(click.ClickException):
        normalize_url("://invalid_url")


def test_remote_errors_and_edge_cases(cli, core, tmp_path):
    from spritzle.cli.config import RemotesConfig

    runner = CliRunner()
    cfg = RemotesConfig(config_dir=tmp_path)
    raw_key, _ = core.key_manager.create_key(name="test")
    daemon_url = f"http://127.0.0.1:{cli.server.port}"

    # Empty remotes list / status
    res_no_remotes = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "status"],
    )
    assert res_no_remotes.exit_code == 1
    assert "No remotes configured." in res_no_remotes.output

    # Add remote
    res_add = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "add", "box1", daemon_url, "--key", raw_key],
    )
    assert res_add.exit_code == 0

    # Add without force fails
    res_dup = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "add", "box1", daemon_url, "--key", raw_key],
    )
    assert res_dup.exit_code == 1
    assert "already exists" in res_dup.output

    # Add with force succeeds
    res_force = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "add", "box1", daemon_url, "--key", raw_key, "--force"],
    )
    assert res_force.exit_code == 0

    # Add with interactive key prompt
    res_prompt = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "add", "box2", daemon_url],
        input=f"{raw_key}\n",
    )
    assert res_prompt.exit_code == 0

    # Add unreachable remote fails
    res_unreach = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "add", "dead", "http://127.0.0.1:1", "--key", raw_key],
    )
    assert res_unreach.exit_code == 1

    # Show nonexistent remote
    res_no_show = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "show", "nonexistent"],
    )
    assert res_no_show.exit_code == 1
    assert "does not exist" in res_no_show.output

    # Show plain
    res_show_plain = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "show", "box1", "--plain"],
    )
    assert res_show_plain.exit_code == 0
    assert "Property" in res_show_plain.output
    assert "Value" in res_show_plain.output
    assert "box1" in res_show_plain.output

    # Use nonexistent remote
    res_use_no = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "use", "nonexistent"],
    )
    assert res_use_no.exit_code == 1
    assert "does not exist" in res_use_no.output

    # Remove nonexistent remote
    res_rm_no = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "remove", "nonexistent"],
    )
    assert res_rm_no.exit_code == 1
    assert "does not exist" in res_rm_no.output

    # Set key for nonexistent remote
    res_set_no = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "set-key", "nonexistent", "dummy_key"],
    )
    assert res_set_no.exit_code == 1
    assert "does not exist" in res_set_no.output

    # Set key with connection failure
    cfg.load()
    cfg.set_remote("deadbox", "http://127.0.0.1:1", "spz_d_dead", "key")
    res_set_dead = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "set-key", "deadbox", "newkey"],
    )
    assert res_set_dead.exit_code == 1

    # Set key with interactive prompt
    res_set_prompt = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "set-key", "box1"],
        input=f"{raw_key}\n",
    )
    assert res_set_prompt.exit_code == 0, res_set_prompt.output

    # Set key with identity mismatch
    cfg.set_remote("fakebox", daemon_url, "spz_d_different_id", raw_key)
    res_mismatch = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "set-key", "fakebox", raw_key],
    )
    assert res_mismatch.exit_code == 1
    assert "Daemon identity mismatch" in res_mismatch.output

    # Status auth_failed check
    cfg.set_remote("bad_auth_box", daemon_url, core.identity.daemon_id, "spritzle_bad_key")
    res_bad_auth = runner.invoke(
        spritzle_cli,
        ["-c", str(tmp_path), "remote", "status", "bad_auth_box", "--json"],
    )
    assert res_bad_auth.exit_code == 0
    bad_auth_data = json.loads(res_bad_auth.output)
    assert bad_auth_data["status"] == "auth_failed"

    # Status with multiple states rendered in rich table (online, auth_failed, id_mismatch, offline)
    res_rich_multi = runner.invoke(
        spritzle_cli,
        ["--color", "-c", str(tmp_path), "remote", "status"],
    )
    assert res_rich_multi.exit_code == 0
    assert "online" in res_rich_multi.output
    assert "auth_failed" in res_rich_multi.output
    assert "id_mismatch" in res_rich_multi.output
    assert "offline" in res_rich_multi.output


def test_run_coroutine_new_loop():
    from unittest.mock import patch
    from spritzle.cli.commands.remote import run_coroutine

    async def sample():
        return 42

    with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
        assert run_coroutine(sample()) == 42


