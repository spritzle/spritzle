import json
from click.testing import CliRunner
from spritzle.cli.main import cli as spritzle_cli


def test_list_commands(cli):
    """
    Test the 'list' command.

    The 'cli' fixture here is the aiohttp test client from tests/conftest.py.
    It has a running server at cli.server.
    """
    runner = CliRunner()

    # Run the 'list' command pointing to our test server
    # We use --token "" to bypass token file checks if any, though the test server might not require it depending on config
    # The default token logic in Client checks for a file if token is empty, but providing empty string usually works if auth is disabled or mocked.
    # Looking at conftest.py, auth doesn't seem explicitly disabled in 'setup_app', need to check.
    # But let's try basic connection first.

    result = runner.invoke(
        spritzle_cli, ["--port", str(cli.server.port), "--token", "test-token", "list"]
    )

    # Ideally, we should add some torrents to the core before listing,
    # but the 'cli' fixture setup (via 'app' -> 'core') creates a fresh core.
    # So the list should be empty or contain what we add.

    assert result.exit_code == 0
    # Depending on output format (table), we should at least see headers or empty state
    # spritzle list defaults to printing a table.
    print(result.output)


def test_stats_command(cli):
    """
    Test the 'stats' command.
    """
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli, ["--port", str(cli.server.port), "--token", "test-token", "stats"]
    )
    assert result.exit_code == 0
    print(result.output)


def test_client_url_formatting():
    from spritzle.cli.main import Client
    client = Client("127.0.0.1", 8080, "/tmp", "token")
    assert client.url("torrent") == "http://127.0.0.1:8080/torrent"
    assert client.url("torrent", "foo=bar") == "http://127.0.0.1:8080/torrent?foo=bar"


def test_client_url_formatting_ipv6():
    from spritzle.cli.main import Client
    from yarl import URL

    client = Client("::1", 8080, "/tmp", "token")
    assert client.url("torrent") == "http://[::1]:8080/torrent"
    assert client.url("torrent", "foo=bar") == "http://[::1]:8080/torrent?foo=bar"
    # Must parse successfully with yarl without ValueError
    u = URL(client.url("torrent"))
    assert u.host == "::1"
    assert u.port == 8080

    # Already bracketed
    client_bracketed = Client("[::1]", 8080, "/tmp", "token")
    assert client_bracketed.url("torrent") == "http://[::1]:8080/torrent"



def test_remove_delete_files_command(cli, loop):
    import libtorrent as lt
    from unittest.mock import patch
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    # Add a torrent first
    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
    info_hash = str(handle.info_hash())


    runner = CliRunner()
    with patch.object(cli.app[APP_KEY_CORE].torrent, "remove", wraps=cli.app[APP_KEY_CORE].torrent.remove) as mock_remove:
        result = runner.invoke(
            spritzle_cli,
            ["--port", str(cli.server.port), "--token", "test-token", "remove", "--delete-files", info_hash]
        )
        assert result.exit_code == 0
        assert mock_remove.called
        # Check that options included delete_files flag
        args, kwargs = mock_remove.call_args
        options = args[1]
        assert bool(options & lt.options_t.delete_files) is True


def test_add_command_option_with_equal_sign(cli):
    from tests.daemon.common import torrent_dir
    t_file = str(torrent_dir / "testtorrent1.torrent")
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "add",
            "-o", "save_path=/tmp/test=path",
            t_file,
        ]
    )
    assert result.exit_code == 0



def test_list_command_missing_field_and_query_equal_sign(cli):
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "list",
            "-f", "name,non_existent_field",
            "-q", "name=test=foo",
        ]
    )
    assert result.exit_code == 0


def test_list_command_non_string_list_field(cli):
    """
    Test that 'list' formatting does not crash with TypeError when a field
    contains a list of non-strings (e.g. integers or non-string items).
    """
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
    info_hash = str(handle.info_hash())

    # Add non-string list field to torrent_data
    cli.app[APP_KEY_CORE].torrent_data[info_hash] = {"custom_ints": [1, 2, 3]}

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "list",
            "-f", "name,custom_ints",
        ],
    )
    assert result.exit_code == 0
    assert "1,2,3" in result.output



def test_config_command_types(cli):
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "config",
            "-s", "auth_timeout", "300",
        ]
    )
    assert result.exit_code == 0
    from spritzle.daemon.keys import APP_KEY_CONFIG
    config = cli.app[APP_KEY_CONFIG]
    assert config["auth_timeout"] == 300
    assert isinstance(config["auth_timeout"], int)


def test_settings_command_boolean_setter(cli):
    from spritzle.daemon.keys import APP_KEY_CORE
    core = cli.app[APP_KEY_CORE]
    # Set to True first
    core.session.apply_settings({"enable_dht": True})
    assert core.session.get_settings()["enable_dht"] is True

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "settings",
            "-s", "enable_dht", "false",
        ]
    )
    assert result.exit_code == 0
    assert core.session.get_settings()["enable_dht"] is False



def test_client_init_with_empty_or_invalid_tokens_file(tmp_path):
    from spritzle.cli.main import Client
    tokens_file = tmp_path / "tokens"
    tokens_file.write_text("")  # empty file

    client = Client("127.0.0.1", 8080, str(tmp_path), "")
    assert client.token == ""

    tokens_file.write_text("not a dictionary")
    client = Client("127.0.0.1", 8080, str(tmp_path), "")
    assert client.token == ""


def test_client_init_with_valid_tokens_file(tmp_path):
    import json
    from spritzle.cli.main import Client
    tokens_file = tmp_path / "tokens"
    tokens_file.write_text(json.dumps({"127.0.0.1:8080": "my-saved-token"}))

    client = Client("127.0.0.1", 8080, str(tmp_path), "")
    assert client.token == "my-saved-token"


def test_auth_command(cli, tmp_path):
    import json
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--config", str(tmp_path),
            "auth",
            "--password", "password",
        ],
    )
    assert result.exit_code == 0
    tokens_file = tmp_path / "tokens"
    assert tokens_file.exists()
    data = json.loads(tokens_file.read_text())
    assert f"127.0.0.1:{cli.server.port}" in data
    assert len(data[f"127.0.0.1:{cli.server.port}"]) > 0


def test_auth_command_nonexistent_config_dir(cli, tmp_path):
    import json
    config_dir = tmp_path / "nonexistent" / "config"
    assert not config_dir.exists()

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--config", str(config_dir),
            "auth",
            "--password", "password",
        ],
    )
    assert result.exit_code == 0
    tokens_file = config_dir / "tokens"
    assert tokens_file.exists()
    data = json.loads(tokens_file.read_text())
    assert f"127.0.0.1:{cli.server.port}" in data


def test_auth_command_corrupted_non_dict_tokens_file(cli, tmp_path):
    tokens_file = tmp_path / "tokens"
    tokens_file.write_text("[1, 2, 3]")  # Non-empty list, truthy but not a dict

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--config", str(tmp_path),
            "auth",
            "--password", "password",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(tokens_file.read_text())
    assert isinstance(data, dict)
    assert f"127.0.0.1:{cli.server.port}" in data


def test_flags_command(cli):
    import libtorrent as lt
    from tests.daemon.common import torrent_dir
    from spritzle.daemon.keys import APP_KEY_CORE

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "flags",
            info_hash,
        ],
    )
    assert result.exit_code == 0
    assert "auto_managed" in result.output

    # Test setting a flag
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "flags",
            info_hash,
            "-s", "auto_managed",
        ],
    )
    assert result.exit_code == 0
    assert bool(handle.flags() & lt.torrent_flags.auto_managed) is True

    # Test unsetting a flag
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "flags",
            info_hash,
            "-u", "auto_managed",
        ],
    )
    assert result.exit_code == 0
    assert bool(handle.flags() & lt.torrent_flags.auto_managed) is False


def test_add_command_nonexistent_file(cli):
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "add",
            "/path/to/nonexistent/file.torrent",
        ],
    )
    assert result.exit_code == 1
    assert "Error reading file" in result.output
    assert "Traceback" not in result.output


def test_add_command_info_hash(cli):
    runner = CliRunner()
    valid_hash = "0123456789abcdef0123456789abcdef01234567"
    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "add",
            valid_hash,
        ],
    )
    assert result.exit_code == 0
    assert "added successfully" in result.output


def test_cli_config_and_flags_send_json_content_type(cli):
    from unittest.mock import patch
    runner = CliRunner()

    with patch.object(cli.app.middlewares[1], "__call__", wraps=cli.app.middlewares[1]) as _:
        pass

    # We can inspect the Content-Type received at the server by patching the route handler or checking ClientSession.patch
    captured_content_types = []

    from aiohttp import ClientSession
    orig_patch = ClientSession.patch
    orig_put = ClientSession.put

    def mock_patch(self, url, **kwargs):
        if "json" in kwargs:
            captured_content_types.append("application/json")
        elif "data" in kwargs:
            captured_content_types.append("data")
        return orig_patch(self, url, **kwargs)

    def mock_put(self, url, **kwargs):
        if "json" in kwargs:
            captured_content_types.append("application/json")
        elif "data" in kwargs:
            captured_content_types.append("data")
        return orig_put(self, url, **kwargs)

    with patch.object(ClientSession, "patch", mock_patch), patch.object(ClientSession, "put", mock_put):
        res1 = runner.invoke(
            spritzle_cli,
            ["--port", str(cli.server.port), "--token", "test-token", "config", "-s", "auth_timeout", "120"],
        )
        assert res1.exit_code == 0
        assert "application/json" in captured_content_types

        captured_content_types.clear()
        import libtorrent as lt
        from tests.daemon.common import torrent_dir
        from spritzle.daemon.keys import APP_KEY_CORE

        t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
        ti = lt.torrent_info(lt.bdecode(t_file))
        handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
        valid_hash = str(handle.info_hash())

        res2 = runner.invoke(
            spritzle_cli,
            ["--port", str(cli.server.port), "--token", "test-token", "flags", valid_hash, "-s", "auto_managed"],
        )
        assert res2.exit_code == 0
        assert "application/json" in captured_content_types


def test_add_command_missing_location_header(cli, monkeypatch):
    import aiohttp
    runner = CliRunner()
    valid_hash = "0123456789abcdef0123456789abcdef01234567"

    orig_post = aiohttp.ClientSession.post

    class MockResponse:
        def __init__(self, real_resp):
            self.real_resp = real_resp
            self.status = real_resp.status
            self.reason = real_resp.reason
            self.headers = {}  # Location header stripped!

        async def json(self):
            return await self.real_resp.json()

    class MockContextManager:
        def __init__(self, real_cm):
            self.real_cm = real_cm

        async def __aenter__(self):
            real_resp = await self.real_cm.__aenter__()
            return MockResponse(real_resp)

        async def __aexit__(self, exc_type, exc, tb):
            return await self.real_cm.__aexit__(exc_type, exc, tb)

    def mock_post(self, url, **kwargs):
        real_cm = orig_post(self, url, **kwargs)
        return MockContextManager(real_cm)

    monkeypatch.setattr(aiohttp.ClientSession, "post", mock_post)

    result = runner.invoke(
        spritzle_cli,
        [
            "--port", str(cli.server.port),
            "--token", "test-token",
            "add",
            valid_hash,
        ],
    )
    assert result.exit_code == 0
    assert "added successfully" in result.output


def test_pause_command(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "pause", info_hash],
    )
    assert result.exit_code == 0
    assert "paused successfully" in result.output


def test_resume_command(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "resume", info_hash],
    )
    assert result.exit_code == 0
    assert "resumed successfully" in result.output


def test_move_storage_command(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--port",
            str(cli.server.port),
            "--token",
            "test-token",
            "move_storage",
            info_hash,
            "/tmp/new_storage",
        ],
    )
    assert result.exit_code == 0
    assert f"Moved storage for {info_hash} to /tmp/new_storage" in result.output


def test_spritzled_token_command(tmp_path):
    import jwt
    from spritzle.daemon.config import Config
    from spritzle.daemon.main import main as daemon_cli

    runner = CliRunner()
    result = runner.invoke(daemon_cli, ["token", "-c", str(tmp_path), "-e", "3600"])
    assert result.exit_code == 0
    token = result.output.strip()
    assert token

    config = Config(config_dir=str(tmp_path))
    decoded = jwt.decode(token, config["auth_secret"], algorithms=["HS256"])
    assert "exp" in decoded


def test_pause_by_name(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "pause", "file1.txt"],
    )
    assert result.exit_code == 0
    assert "paused successfully" in result.output
    assert info_hash in result.output


def test_pause_ambiguous_name(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    t2 = (torrent_dir / "testtorrent2.torrent").read_bytes()
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t2)), "save_path": "/tmp"})

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "pause", "file"],
    )
    assert result.exit_code == 1
    assert "Multiple torrents match 'file'" in result.output


def test_pause_nonexistent_name(cli):
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "pause", "nonexistent_torrent"],
    )
    assert result.exit_code == 1
    assert "No torrent found matching 'nonexistent_torrent'" in result.output


def test_pause_query_and_all(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    t2 = (torrent_dir / "testtorrent2.torrent").read_bytes()
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t2)), "save_path": "/tmp"})

    runner = CliRunner()
    # Pause by query
    result = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "pause", "-q", "name=file1.*"],
    )
    assert result.exit_code == 0
    assert "Paused 1 torrents successfully" in result.output

    # Pause by --all
    result_all = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "pause", "--all"],
    )
    assert result_all.exit_code == 0
    assert "Paused 2 torrents successfully" in result_all.output


def test_resume_by_name_and_query(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    t2 = (torrent_dir / "testtorrent2.torrent").read_bytes()
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t2)), "save_path": "/tmp"})

    runner = CliRunner()
    # Resume single by name
    result = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "resume", "file1.txt"],
    )
    assert result.exit_code == 0
    assert "resumed successfully" in result.output

    # Resume by query
    result_q = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "resume", "-q", "name=file.*"],
    )
    assert result_q.exit_code == 0
    assert "Resumed 2 torrents successfully" in result_q.output

    # Resume by --all
    result_all = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "resume", "--all"],
    )
    assert result_all.exit_code == 0
    assert "Resumed 2 torrents successfully" in result_all.output


def test_remove_by_name_and_query(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    t2 = (torrent_dir / "testtorrent2.torrent").read_bytes()
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t2)), "save_path": "/tmp"})

    runner = CliRunner()
    # Remove single by name
    result = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "remove", "file1.txt"],
    )
    assert result.exit_code == 0
    assert "removed successfully" in result.output

    # 1 torrent should remain
    assert len(cli.app[APP_KEY_CORE].session.get_torrents()) == 1

    # Remove remaining by --all
    result_all = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "remove", "--all"],
    )
    assert result_all.exit_code == 0
    assert "Removed 1 torrents successfully" in result_all.output
    assert len(cli.app[APP_KEY_CORE].session.get_torrents()) == 0


def test_flags_by_name_and_query(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})

    runner = CliRunner()
    # Show flags by name
    res_show = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "flags", "file1.txt"],
    )
    assert res_show.exit_code == 0
    assert "auto_managed" in res_show.output

    # Set flags by name
    res_set = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "flags", "file1.txt", "-s", "auto_managed"],
    )
    assert res_set.exit_code == 0

    # Set flags by query
    res_query = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "flags", "-q", "name=file1.*", "-u", "auto_managed"],
    )
    assert res_query.exit_code == 0


def test_move_storage_by_name(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    res = runner.invoke(
        spritzle_cli,
        [
            "--port",
            str(cli.server.port),
            "--token",
            "test-token",
            "move_storage",
            "file1.txt",
            "/tmp/moved_storage",
        ],
    )
    assert res.exit_code == 0
    assert f"Moved storage for {info_hash} to /tmp/moved_storage" in res.output


def test_display_formatters():
    from spritzle.cli.display import (
        format_bool,
        format_bytes,
        format_progress,
        format_speed,
        format_state,
        should_use_color,
    )

    # State colors requested by user
    assert format_state("downloading", use_color=True) == "[green]downloading[/green]"
    assert format_state("seeding", use_color=True) == "[blue]seeding[/blue]"
    assert format_state("checking", use_color=True) == "[magenta]checking[/magenta]"
    assert format_state("checking_files", use_color=True) == "[magenta]checking_files[/magenta]"
    assert format_state("queued", use_color=True) == "[yellow]queued[/yellow]"
    assert format_state("paused", use_color=True) == "[dim]paused[/dim]"
    assert format_state("error", use_color=True) == "[red]error[/red]"
    # No color mode
    assert format_state("downloading", use_color=False) == "downloading"

    # Speeds
    assert format_speed(0, human=True) == "0 B/s"
    assert format_speed(1024, human=True) == "1.0 KB/s"
    assert format_speed(1048576, human=True) == "1.0 MB/s"
    assert format_speed(1048576, human=False) == "1048576"

    # Bytes
    assert format_bytes(500, human=True) == "500 B"
    assert format_bytes(1048576, human=True) == "1.0 MB"
    assert format_bytes(1073741824, human=True) == "1.0 GB"
    assert format_bytes(1073741824, human=False) == "1073741824"

    # Progress
    assert format_progress(0.5, human=True) == "[█████░░░░░] 50.0%"
    assert format_progress(1.0, human=True) == "[██████████] 100.0%"
    assert format_progress(0.5, human=False) == "0.5"

    # Booleans
    assert "on" in format_bool(True, human=True, use_color=True)
    assert "off" in format_bool(False, human=True, use_color=True)
    assert format_bool(True, human=False) == "True"
    # Ensure Rich markup renders [on] and [off] as visible text badges
    from rich.console import Console as TestConsole
    tc = TestConsole(no_color=True, force_terminal=False)
    assert tc.render_str(format_bool(True, human=True, use_color=True)).plain == "[on]"
    assert tc.render_str(format_bool(False, human=True, use_color=True)).plain == "[off]"

    # Color overrides
    assert should_use_color(color_opt=True) is True
    assert should_use_color(color_opt=False) is False


def test_list_json_output(cli):
    import json
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})

    runner = CliRunner()
    res = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "list", "--json"],
    )
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "file1.txt"
    assert "state" in data[0]
    assert "progress" in data[0]


def test_list_plain_and_color_flags(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})

    runner = CliRunner()
    # Plain mode
    res_plain = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "list", "--plain"],
    )
    assert res_plain.exit_code == 0
    assert "file1.txt" in res_plain.output

    # Color enabled mode
    res_color = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "--color", "list"],
    )
    assert res_color.exit_code == 0
    assert "file1.txt" in res_color.output


def test_flags_json_and_plain(cli):
    import json
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})

    runner = CliRunner()
    # JSON mode
    res_json = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "flags", "file1.txt", "--json"],
    )
    assert res_json.exit_code == 0
    flags_dict = json.loads(res_json.output)
    assert isinstance(flags_dict, dict)
    assert "auto_managed" in flags_dict

    # Plain mode
    res_plain = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "flags", "file1.txt", "--plain"],
    )
    assert res_plain.exit_code == 0
    assert "auto_managed" in res_plain.output


def test_stats_and_settings_json(cli):
    import json
    runner = CliRunner()

    # Stats JSON
    res_stats = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "stats", "--json"],
    )
    assert res_stats.exit_code == 0
    stats_data = json.loads(res_stats.output)
    assert isinstance(stats_data, dict)

    # Settings JSON
    res_settings = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--json"],
    )
    assert res_settings.exit_code == 0
    settings_data = json.loads(res_settings.output)
    assert isinstance(settings_data, dict)


def test_settings_defaults_and_modified_flags(cli):
    import json
    runner = CliRunner()

    # Reset all first to ensure clean state
    runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--reset-all"],
    )

    # Defaults flag
    res_def = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--defaults", "--json"],
    )
    assert res_def.exit_code == 0
    defaults = json.loads(res_def.output)
    assert "download_rate_limit" in defaults

    # Modified flag when nothing modified
    res_mod_none = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--modified"],
    )
    assert res_mod_none.exit_code == 0
    assert "No settings have been modified" in res_mod_none.output

    # Modify a setting
    res_set = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "-s", "download_rate_limit", "500000"],
    )
    assert res_set.exit_code == 0

    # Modified flag should now show only the modified setting
    res_mod = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--modified", "--json"],
    )
    assert res_mod.exit_code == 0
    mod_data = json.loads(res_mod.output)
    assert list(mod_data.keys()) == ["download_rate_limit"]
    assert mod_data["download_rate_limit"] == 500000

    # Clean up
    runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--reset", "download_rate_limit"],
    )


def test_settings_reset_commands(cli):
    runner = CliRunner()

    # Reset specific key
    runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "-s", "download_rate_limit", "999999"],
    )
    res_reset = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--reset", "download_rate_limit"],
    )
    assert res_reset.exit_code == 0
    assert "download_rate_limit" in res_reset.output

    # Verify download_rate_limit was reset
    res_check = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--modified"],
    )
    assert "download_rate_limit" not in res_check.output

    # Reset all
    runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "-s", "download_rate_limit", "1111", "-s", "upload_rate_limit", "2222"],
    )
    res_reset_all = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--reset-all"],
    )
    assert res_reset_all.exit_code == 0
    assert "Reset all" in res_reset_all.output

    # After reset all, nothing is modified from baseline
    res_after_all = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--modified"],
    )
    assert "No settings have been modified" in res_after_all.output


def test_settings_visual_modified_indicator(cli):
    runner = CliRunner()

    # Modify download_rate_limit
    res_set = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "-s", "download_rate_limit", "777777"],
    )
    assert res_set.exit_code == 0, res_set.output

    # Invoke with color
    res = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "--color", "settings"],
    )
    assert res.exit_code == 0
    assert "* download_rate_limit" in res.output or "* download_rate_" in res.output
    assert "modified from default" in res.output

    # Clean up
    runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "settings", "--reset-all"],
    )


def test_quiet_action_commands(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    # Pause with --quiet
    res_pause = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "pause", "-Q", "file1.txt"],
    )
    assert res_pause.exit_code == 0
    assert res_pause.output.strip() == info_hash

    # Resume with --quiet
    res_resume = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "resume", "--quiet", "file1.txt"],
    )
    assert res_resume.exit_code == 0
    assert res_resume.output.strip() == info_hash

    # Remove with --quiet
    res_remove = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "remove", "-Q", "file1.txt"],
    )
    assert res_remove.exit_code == 0
    assert res_remove.output.strip() == info_hash


def test_render_kv_table_multi_column():
    import io
    from rich.console import Console
    from spritzle.cli.display import render_kv_table

    items = [
        ("item_0", "val_0"),
        ("item_1", "val_1"),
        ("item_2", "val_2"),
        ("item_3", "val_3"),
        ("empty_str", ""),
        ("bool_flag", True),
    ]

    # Wide console (>= 140) -> 3 column pairs
    buf_wide = io.StringIO()
    c_wide = Console(file=buf_wide, width=150, force_terminal=True)
    render_kv_table(c_wide, items, title="Wide Table")
    output_wide = buf_wide.getvalue()
    assert "Wide Table" in output_wide
    assert "item_0" in output_wide
    assert "item_3" in output_wide
    assert '""' in output_wide
    assert "[on]" in output_wide

    # Medium console (80-139) -> 2 column pairs
    buf_med = io.StringIO()
    c_med = Console(file=buf_med, width=90, force_terminal=True)
    render_kv_table(c_med, items, title="Medium Table")
    output_med = buf_med.getvalue()
    assert "Medium Table" in output_med

    # Narrow console (< 80) -> 1 column pair
    buf_narrow = io.StringIO()
    c_narrow = Console(file=buf_narrow, width=60, force_terminal=True)
    render_kv_table(c_narrow, items, title="Narrow Table")
    output_narrow = buf_narrow.getvalue()
    assert "Narrow Table" in output_narrow


def test_config_json_and_plain(cli):
    import json
    runner = CliRunner()

    # JSON mode
    res_json = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "config", "--json"],
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert isinstance(data, dict)
    assert "auth_timeout" in data

    # Plain mode
    res_plain = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "config", "--plain"],
    )
    assert res_plain.exit_code == 0
    assert "auth_timeout" in res_plain.output

    # Color mode
    res_color = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "--color", "config"],
    )
    assert res_color.exit_code == 0
    assert "Spritzle Configuration" in res_color.output


def test_add_quiet(cli):
    from tests.daemon.common import torrent_dir

    t_file = str(torrent_dir / "testtorrent1.torrent")
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["--port", str(cli.server.port), "--token", "test-token", "add", "-Q", t_file],
    )
    assert result.exit_code == 0
    added_hash = result.output.strip()
    assert len(added_hash) == 40
    int(added_hash, 16)  # Valid hex


def test_help_command():
    runner = CliRunner()

    # General help
    res_general = runner.invoke(spritzle_cli, ["help"])
    assert res_general.exit_code == 0
    assert "Usage:" in res_general.output
    assert "Tip: Run 'spritzle help <command>'" in res_general.output

    # Command-specific help with examples
    res_cmd = runner.invoke(spritzle_cli, ["help", "pause"])
    assert res_cmd.exit_code == 0
    assert "Usage:" in res_cmd.output
    assert "--query" in res_cmd.output
    assert "Examples:" in res_cmd.output
    assert "spritzle pause" in res_cmd.output

    # Nonexistent command
    res_err = runner.invoke(spritzle_cli, ["help", "nonexistent"])
    assert res_err.exit_code == 1
    assert "No such command 'nonexistent'" in res_err.output

    # Color mode
    res_color = runner.invoke(spritzle_cli, ["--color", "help", "list"])
    assert res_color.exit_code == 0
    assert "Examples:" in res_color.output













