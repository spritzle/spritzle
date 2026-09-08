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







