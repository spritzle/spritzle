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


def test_client_init_with_empty_or_invalid_tokens_file(tmp_path):
    from spritzle.cli.main import Client
    tokens_file = tmp_path / "tokens"
    tokens_file.write_text("")  # empty file

    client = Client("127.0.0.1", 8080, str(tmp_path), "")
    assert client.token == ""

    tokens_file.write_text("not a dictionary")
    client = Client("127.0.0.1", 8080, str(tmp_path), "")
    assert client.token == ""




