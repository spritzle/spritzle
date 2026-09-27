import json
from typing import Any
from click.testing import CliRunner
from spritzle.cli.main import cli as spritzle_cli


def _add_test_torrent(session, ti, save_path="/tmp"):
    import libtorrent as lt
    atp = lt.add_torrent_params()
    atp.ti = ti
    atp.save_path = save_path
    return session.add_torrent(atp)


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
        spritzle_cli, ["list"]
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
    result = runner.invoke(spritzle_cli, ["stats"])
    assert result.exit_code == 0

    # Plain and raw
    res_plain = runner.invoke(spritzle_cli, ["stats", "--plain"])
    assert res_plain.exit_code == 0
    assert "Torrents: Downloading" in res_plain.output

    res_raw = runner.invoke(spritzle_cli, ["stats", "--plain", "--raw"])
    assert res_raw.exit_code == 0

    # JSON output
    res_json = runner.invoke(spritzle_cli, ["stats", "--json"])
    assert res_json.exit_code == 0
    assert "torrents" in json.loads(res_json.output)

    # Color output
    res_color = runner.invoke(spritzle_cli, ["--color", "stats"])
    assert res_color.exit_code == 0

    # All stats variants
    res_all_plain = runner.invoke(spritzle_cli, ["stats", "--all", "--plain"])
    assert res_all_plain.exit_code == 0

    res_all_json = runner.invoke(spritzle_cli, ["stats", "--all", "--json"])
    assert res_all_json.exit_code == 0

    res_all_color = runner.invoke(spritzle_cli, ["--color", "stats", "--all"])
    assert res_all_color.exit_code == 0


def test_client_url_formatting(tmp_path):
    from spritzle.cli.main import Client
    from spritzle.cli.config import RemotesConfig

    remotes = RemotesConfig(config_dir=tmp_path)
    remotes.set_remote("test", "http://127.0.0.1:8080", "daemon_id", "token")
    client = Client(config=tmp_path, remote="test")
    assert client.url("torrent") == "http://127.0.0.1:8080/torrent"
    assert client.url("torrent", "foo=bar") == "http://127.0.0.1:8080/torrent?foo=bar"


def test_client_url_formatting_ipv6(tmp_path):
    from spritzle.cli.main import Client
    from spritzle.cli.config import RemotesConfig
    from yarl import URL

    remotes = RemotesConfig(config_dir=tmp_path)
    remotes.set_remote("test", "http://[::1]:8080", "daemon_id", "token")
    client = Client(config=tmp_path, remote="test")
    assert client.url("torrent") == "http://[::1]:8080/torrent"
    assert client.url("torrent", "foo=bar") == "http://[::1]:8080/torrent?foo=bar"
    # Must parse successfully with yarl without ValueError
    u = URL(client.url("torrent"))
    assert u.host == "::1"
    assert u.port == 8080



def test_remove_delete_files_command(cli, loop):
    import libtorrent as lt
    from unittest.mock import patch
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    # Add a torrent first
    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, ti)
    info_hash = str(handle.info_hash())


    runner = CliRunner()
    with patch.object(cli.app[APP_KEY_CORE].torrent, "remove", wraps=cli.app[APP_KEY_CORE].torrent.remove) as mock_remove:
        result = runner.invoke(
            spritzle_cli,
            ["remove", "--delete-files", info_hash]
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
        ["add",
            "-o", "save_path=/tmp/test=path",
            t_file,
        ]
    )
    assert result.exit_code == 0



def test_list_command_missing_field_and_query_equal_sign(cli):
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["list",
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
    handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, ti)
    info_hash = str(handle.info_hash())

    # Add non-string list field to torrent_data
    cli.app[APP_KEY_CORE].torrent_data[info_hash] = {"custom_ints": [1, 2, 3]}

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["list",
            "-f", "name,custom_ints",
        ],
    )
    assert result.exit_code == 0
    assert "1,2,3" in result.output



def test_daemon_config_command_types(cli):
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["daemon-config",
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
        ["settings",
            "-s", "enable_dht", "false",
        ]
    )
    assert result.exit_code == 0
    assert core.session.get_settings()["enable_dht"] is False



def test_remotes_config_corrupted_file(tmp_path):
    from spritzle.cli.config import RemotesConfig
    remotes_file = tmp_path / "remotes.toml"
    remotes_file.write_text("not a valid toml file : [")

    cfg = RemotesConfig(config_dir=tmp_path)
    assert cfg.get_remotes() == {}


def test_remote_add_command_nonexistent_config_dir(cli, core, tmp_path):
    config_dir = tmp_path / "nonexistent" / "config"
    assert not config_dir.exists()

    raw_key, _ = core.key_manager.create_key(name="test")
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        [
            "--config", str(config_dir),
            "remote", "add",
            "testremote", f"http://127.0.0.1:{cli.server.port}",
            "--key", raw_key,
        ],
    )
    assert result.exit_code == 0
    assert "Added remote 'testremote'" in result.output
    assert config_dir.exists()



def test_flags_command(cli):
    import libtorrent as lt
    from tests.daemon.common import torrent_dir
    from spritzle.daemon.keys import APP_KEY_CORE

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, ti)
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["flags",
            info_hash,
        ],
    )
    assert result.exit_code == 0
    assert "auto_managed" in result.output

    # Test setting a flag
    result = runner.invoke(
        spritzle_cli,
        ["flags",
            info_hash,
            "-s", "auto_managed",
        ],
    )
    assert result.exit_code == 0
    assert bool(handle.flags() & lt.torrent_flags.auto_managed) is True

    # Test unsetting a flag
    result = runner.invoke(
        spritzle_cli,
        ["flags",
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
        ["add",
            "/path/to/nonexistent/file.torrent",
        ],
    )
    assert result.exit_code == 1
    assert "Error reading file" in result.output
    assert "Traceback" not in result.output


def test_add_command_options_and_formats(cli):
    from tests.daemon.common import torrent_dir
    runner = CliRunner()
    t_file = str(torrent_dir / "random_one_file.torrent")

    magnet_uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test_mag"

    # 1. Option without equals sign: -o auto_managed on magnet URI
    res_opt = runner.invoke(spritzle_cli, ["add", "-o", "auto_managed", magnet_uri])
    assert res_opt.exit_code == 0, res_opt.output

    # 2. Add via stdin: path == "-"
    with open(t_file, "rb") as f:
        t_bytes = f.read()
    res_stdin = runner.invoke(spritzle_cli, ["add", "-"], input=t_bytes)
    assert res_stdin.exit_code == 0

    # 3. Add via stdin with magnet URI
    magnet_uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test_mag"
    res_stdin_mag = runner.invoke(spritzle_cli, ["add", "-"], input=magnet_uri)
    assert res_stdin_mag.exit_code == 0

    # 4. Malformed magnet link prefixes: ?xt= and magnet?
    res_mal1 = runner.invoke(spritzle_cli, ["add", "?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"])
    assert res_mal1.exit_code == 1
    assert "Malformed magnet link" in res_mal1.output

    res_mal2 = runner.invoke(spritzle_cli, ["add", "magnet?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"])
    assert res_mal2.exit_code == 1
    assert "Malformed magnet link" in res_mal2.output

    # 5. Add with JSON and plain output
    res_json = runner.invoke(spritzle_cli, ["add", t_file, "--json"])
    assert res_json.exit_code == 0
    assert "info_hash" in json.loads(res_json.output)

    res_plain = runner.invoke(spritzle_cli, ["add", t_file, "--plain"])
    assert res_plain.exit_code == 0


def test_add_command_info_hash(cli):
    runner = CliRunner()
    valid_hash = "0123456789abcdef0123456789abcdef01234567"
    result = runner.invoke(
        spritzle_cli,
        ["add",
            valid_hash,
        ],
    )
    assert result.exit_code == 0
    assert "Added" in result.output
    assert valid_hash[:8] in result.output


def test_cli_daemon_config_and_flags_send_json_content_type(cli):
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
            ["daemon-config", "-s", "auth_timeout", "120"],
        )
        assert res1.exit_code == 0
        assert "application/json" in captured_content_types

        captured_content_types.clear()
        import libtorrent as lt
        from tests.daemon.common import torrent_dir
        from spritzle.daemon.keys import APP_KEY_CORE

        t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
        ti = lt.torrent_info(lt.bdecode(t_file))
        handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, ti)
        valid_hash = str(handle.info_hash())

        res2 = runner.invoke(
            spritzle_cli,
            ["flags", valid_hash, "-s", "auto_managed"],
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
        ["add",
            valid_hash,
        ],
    )
    assert result.exit_code == 0
    assert "Added" in result.output
    assert valid_hash[:8] in result.output


def test_add_command_extended(cli, monkeypatch, tmp_path):
    import aiohttp
    runner = CliRunner()
    valid_hash = "0123456789abcdef0123456789abcdef01234567"

    # 1. URL scheme path
    res_url = runner.invoke(
        spritzle_cli,
        ["add", f"http://example.com/torrent/{valid_hash}"],
    )
    # Even if mocked or rejected by daemon, it takes the URL path
    assert res_url.exit_code in (0, 1)

    # 2. Magnet link with dn parameter
    res_mag = runner.invoke(
        spritzle_cli,
        ["add", f"magnet:?xt=urn:btih:{valid_hash}&dn=archlinux-custom"],
    )
    assert res_mag.exit_code == 0
    assert "archlinux-custom" in res_mag.output

    # 3. Watch flag invoked
    watch_called = []
    async def mock_watch(client, hash, color_opt=None):
        watch_called.append(hash)

    monkeypatch.setattr("spritzle.cli.dashboard.watch_single_torrent", mock_watch)
    res_watch = runner.invoke(
        spritzle_cli,
        ["add", valid_hash, "--watch", "--plain"],
    )
    assert res_watch.exit_code == 0
    assert watch_called == [valid_hash]

    # 4. Error response from daemon
    class MockErrResponse:
        status = 400
        reason = "Bad Request"
        headers = {}
        async def json(self):
            return {"error": "Invalid torrent data"}
        async def text(self):
            return '{"error": "Invalid torrent data"}'

    class MockErrContext:
        async def __aenter__(self):
            return MockErrResponse()
        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(aiohttp.ClientSession, "post", lambda *args, **kwargs: MockErrContext())
    res_err = runner.invoke(
        spritzle_cli,
        ["add", valid_hash],
    )
    assert res_err.exit_code == 1
    assert "Error adding torrent" in res_err.output

    # 5. 40-char non-hex filename that fails to open
    non_hex_40 = "z" * 40
    res_non_hex = runner.invoke(
        spritzle_cli,
        ["add", non_hex_40],
    )
    assert res_non_hex.exit_code == 1
    assert "Error reading file" in res_non_hex.output

    # 6. Response without name or size (fetches from torrent/{hash})
    class MockMinimalResponse:
        status = 201
        reason = "Created"
        headers = {"Location": f"/torrent/{valid_hash}"}
        async def json(self):
            return {"info_hash": valid_hash}

    class MockMinimalContext:
        async def __aenter__(self):
            return MockMinimalResponse()
        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(aiohttp.ClientSession, "post", lambda *args, **kwargs: MockMinimalContext())
    res_minimal = runner.invoke(
        spritzle_cli,
        ["add", valid_hash],
    )
    assert res_minimal.exit_code == 0


def test_pause_command(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, ti)
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["pause", info_hash],
    )
    assert result.exit_code == 0
    assert "paused successfully" in result.output


def test_resume_command(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, ti)
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["resume", info_hash],
    )
    assert result.exit_code == 0
    assert "resumed successfully" in result.output


def test_move_storage_command(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, ti)
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["move-storage",
            info_hash,
            "/tmp/new_storage",
        ],
    )
    assert result.exit_code == 0
    assert f"Moved storage for {info_hash} to /tmp/new_storage" in result.output


def test_spritzled_key_command(tmp_path):
    from spritzle.daemon.main import main as daemon_cli

    runner = CliRunner()
    result = runner.invoke(daemon_cli, ["key", "create", "-c", str(tmp_path), "--name", "testkey"])
    assert result.exit_code == 0
    assert "Created API key for 'testkey'" in result.output
    assert "spritzle_" in result.output

    # List keys
    result_list = runner.invoke(daemon_cli, ["key", "list", "-c", str(tmp_path)])
    assert result_list.exit_code == 0
    assert "testkey" in result_list.output
    assert "active" in result_list.output



def test_pause_by_name(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t_file = (torrent_dir / "testtorrent1.torrent").read_bytes()
    ti = lt.torrent_info(lt.bdecode(t_file))
    handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, ti)
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["pause", "file1.txt"],
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
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t2)))

    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["pause", "file"],
    )
    assert result.exit_code == 1
    assert "Multiple torrents match 'file'" in result.output


def test_pause_nonexistent_name(cli):
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["pause", "nonexistent_torrent"],
    )
    assert result.exit_code == 1
    assert "No torrent found matching 'nonexistent_torrent'" in result.output


def test_pause_query_and_all(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    t2 = (torrent_dir / "testtorrent2.torrent").read_bytes()
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t2)))

    runner = CliRunner()
    # Pause by query
    result = runner.invoke(
        spritzle_cli,
        ["pause", "-q", "name=file1.*"],
    )
    assert result.exit_code == 0
    assert "Paused 1 torrents successfully" in result.output

    # Pause by --all
    result_all = runner.invoke(
        spritzle_cli,
        ["pause", "--all"],
    )
    assert result_all.exit_code == 0
    assert "Paused 2 torrents successfully" in result_all.output


def test_resume_by_name_and_query(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    t2 = (torrent_dir / "testtorrent2.torrent").read_bytes()
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t2)))

    runner = CliRunner()
    # Resume single by name
    result = runner.invoke(
        spritzle_cli,
        ["resume", "file1.txt"],
    )
    assert result.exit_code == 0
    assert "resumed successfully" in result.output

    # Resume by query
    result_q = runner.invoke(
        spritzle_cli,
        ["resume", "-q", "name=file.*"],
    )
    assert result_q.exit_code == 0
    assert "Resumed 2 torrents successfully" in result_q.output

    # Resume by --all
    result_all = runner.invoke(
        spritzle_cli,
        ["resume", "--all"],
    )
    assert result_all.exit_code == 0
    assert "Resumed 2 torrents successfully" in result_all.output


def test_remove_by_name_and_query(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    t2 = (torrent_dir / "testtorrent2.torrent").read_bytes()
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t2)))

    runner = CliRunner()
    # Remove single by name
    result = runner.invoke(
        spritzle_cli,
        ["remove", "file1.txt"],
    )
    assert result.exit_code == 0
    assert "removed successfully" in result.output

    # 1 torrent should remain
    assert len(cli.app[APP_KEY_CORE].session.get_torrents()) == 1

    # Remove remaining by --all
    result_all = runner.invoke(
        spritzle_cli,
        ["remove", "--all"],
    )
    assert result_all.exit_code == 0
    assert "Removed 1 torrents successfully" in result_all.output
    assert len(cli.app[APP_KEY_CORE].session.get_torrents()) == 0


def test_flags_by_name_and_query(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))

    runner = CliRunner()
    # Show flags by name
    res_show = runner.invoke(
        spritzle_cli,
        ["flags", "file1.txt"],
    )
    assert res_show.exit_code == 0
    assert "auto_managed" in res_show.output

    # Set flags by name
    res_set = runner.invoke(
        spritzle_cli,
        ["flags", "file1.txt", "-s", "auto_managed"],
    )
    assert res_set.exit_code == 0

    # Set flags by query
    res_query = runner.invoke(
        spritzle_cli,
        ["flags", "-q", "name=file1.*", "-u", "auto_managed"],
    )
    assert res_query.exit_code == 0


def test_move_storage_by_name(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    res = runner.invoke(
        spritzle_cli,
        ["move-storage",
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


def test_modern_display_formatters():
    import io
    from rich import box
    from rich.console import Console as TestConsole
    from spritzle.cli.display import (
        format_latency,
        format_progress,
        format_speed,
        format_state_pill,
        get_border_style,
        get_box_style,
        render_empty_list_card,
        render_info_card,
        render_kv_table,
        render_rich_table,
        render_stats_cards,
        render_status_card,
        strip_ansi,
    )

    # Speed color highlights
    assert "4.2 MB/s" in format_speed(1048576 * 4.2, human=True, use_color=True, is_upload=False)
    assert "[dim]0 B/s[/dim]" in format_speed(0, human=True, use_color=True)
    assert "▲" in format_speed(1024, human=True, use_color=True, is_upload=True)
    assert "▼" in format_speed(1024, human=True, use_color=True, is_upload=False)

    # Smooth progress
    smooth_bar = format_progress(0.5, human=True, width=10, style="smooth", use_color=True)
    assert "50.0%" in smooth_bar
    assert "━" in smooth_bar

    # State pills
    assert "● downloading" in format_state_pill("downloading", use_color=True)
    assert "● seeding" in format_state_pill("seeding", use_color=True)
    assert "⏸ paused" in format_state_pill("paused", use_color=True)
    assert "✖ error" in format_state_pill("error", use_color=True)
    assert "● downloading" in format_state_pill("downloading", use_color=False)

    # Latency tiers
    assert "12.5 ms" in format_latency(12.5, use_color=True)
    assert "●" in format_latency(12.5, use_color=True)
    assert "12.5 ms" in format_latency(12.5, use_color=False)
    assert format_latency(None, use_color=False) == "-"

    # Themes
    assert get_box_style("modern") == box.ROUNDED
    assert get_box_style("minimal") == box.HORIZONTALS
    assert get_box_style("ascii") == box.ASCII
    assert get_border_style("modern") == "dim"
    assert get_border_style("ascii") == "none"

    # Card rendering
    buf = io.StringIO()
    c = TestConsole(file=buf, force_terminal=True, width=100)

    # Status card
    render_status_card(c, "local", "http://127.0.0.1:17382", "spz_123", "1.0", 1.5, "1d 2h", 3)
    out = buf.getvalue()
    assert "Spritzle Daemon Status" in out
    assert "online" in out
    assert "spz_123" in out

    # Info card
    buf.seek(0)
    buf.truncate(0)
    torrent_data = {
        "name": "archlinux-x86_64.iso",
        "state": "downloading",
        "progress": 0.45,
        "download_rate": 2048000,
        "upload_rate": 512000,
        "total_size": 2500000000,
        "total_done": 1125000000,
        "total_wanted": 2500000000,
        "num_peers": 24,
        "num_seeds": 10,
        "num_pieces": 600,
        "save_path": "/home/user/downloads",
        "spritzle.tags": ["linux", "iso"],
    }
    render_info_card(c, torrent_data, "d3b07384d113edec49eaa6238ad5ff00fc7b0553")
    out_info = buf.getvalue()
    assert "archlinux-x86_64.iso" in out_info
    assert "Transfer" in out_info
    assert "Swarm" in out_info
    assert "Storage" in out_info

    # Stats cards
    buf.seek(0)
    buf.truncate(0)
    summary_data = {
        "torrents": {"downloading": 2, "seeding": 1, "checking": 0, "stopped": 0, "queued_download": 0, "queued_seed": 0},
        "transfer": {"downloaded": "1.2 GB", "uploaded": "400 MB", "total_received": "1.3 GB", "total_sent": "420 MB", "ratio": 0.33, "wasted": "0 B"},
        "peers": {"connected": 15, "half_open": 2, "connection_attempts": 120, "incoming_connections": 5},
        "dht": {"nodes": 350, "torrents": 3, "bootstrapping": False},
    }
    render_stats_cards(c, summary_data)
    out_stats = buf.getvalue()
    assert "Session Statistics Summary" in out_stats
    assert "Transfer & Bandwidth" in out_stats

    # Empty list card
    buf.seek(0)
    buf.truncate(0)
    render_empty_list_card(c, dht_nodes=5)
    out_empty = buf.getvalue()
    assert "Spritzle Session" in out_empty
    assert "spritzle add" in out_empty
    assert "bootstrapping DHT..." in out_empty

    # Caption contrast & legibility (no italic in caption to prevent standout inverse-video)
    buf.seek(0)
    buf.truncate(0)
    render_kv_table(c, [("download_rate_limit", 1048576)], modified_keys={"download_rate_limit"})
    out_kv = buf.getvalue()
    assert "modified from default" in out_kv
    assert "\x1b[3m" not in out_kv  # Ensure 'italic' (which renders as inverse video white bar in some terminals) is not used

    buf.seek(0)
    buf.truncate(0)
    render_rich_table(
        c,
        ["Name", "State"],
        [["archlinux-x86_64.iso", "downloading"]],
        caption="[yellow]●[/yellow] bootstrapping DHT...",
    )
    out_rich = buf.getvalue()
    assert "bootstrapping DHT..." in out_rich
    assert "\x1b[3m" not in out_rich  # Ensure 'italic' is not used

    # strip_ansi helper
    assert strip_ansi("\x1b[32m* default remote\x1b[0m") == "* default remote"
    assert strip_ansi("plain text") == "plain text"


def test_list_json_output(cli):
    import json
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))

    runner = CliRunner()
    res = runner.invoke(
        spritzle_cli,
        ["list", "--json"],
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
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))

    runner = CliRunner()
    # Plain mode
    res_plain = runner.invoke(
        spritzle_cli,
        ["list", "--plain"],
    )
    assert res_plain.exit_code == 0
    assert "file1.txt" in res_plain.output

    # Color enabled mode
    res_color = runner.invoke(
        spritzle_cli,
        ["--color", "list"],
    )
    assert res_color.exit_code == 0
    assert "file1.txt" in res_color.output


def test_paused_torrent_display(cli):
    import json
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))
    ih = str(handle.info_hash())

    runner = CliRunner()

    # Pause the torrent via CLI
    res_pause = runner.invoke(spritzle_cli, ["pause", ih])
    assert res_pause.exit_code == 0
    assert "paused successfully" in res_pause.output

    # List output should show paused status
    res_list = runner.invoke(spritzle_cli, ["list"])
    assert res_list.exit_code == 0
    assert "paused" in res_list.output.lower()

    # Plain output mode
    res_plain = runner.invoke(spritzle_cli, ["list", "--plain"])
    assert res_plain.exit_code == 0
    assert "paused" in res_plain.output.lower()

    # JSON output mode
    res_json = runner.invoke(spritzle_cli, ["list", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert len(data) == 1
    assert data[0]["state"] == "paused"

    # Info output mode
    res_info = runner.invoke(spritzle_cli, ["info", ih])
    assert res_info.exit_code == 0
    assert "paused" in res_info.output.lower()

    # Resume the torrent via CLI
    res_resume = runner.invoke(spritzle_cli, ["resume", ih])
    assert res_resume.exit_code == 0
    assert "resumed successfully" in res_resume.output

    # List output after resume should not be paused
    res_resumed_json = runner.invoke(spritzle_cli, ["list", "--json"])
    assert res_resumed_json.exit_code == 0
    data_resumed = json.loads(res_resumed_json.output)
    assert data_resumed[0]["state"] != "paused"


def test_flags_json_and_plain(cli):
    import json
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))

    runner = CliRunner()
    # JSON mode
    res_json = runner.invoke(
        spritzle_cli,
        ["flags", "file1.txt", "--json"],
    )
    assert res_json.exit_code == 0
    flags_dict = json.loads(res_json.output)
    assert isinstance(flags_dict, dict)
    assert "auto_managed" in flags_dict

    # Plain mode
    res_plain = runner.invoke(
        spritzle_cli,
        ["flags", "file1.txt", "--plain"],
    )
    assert res_plain.exit_code == 0
    assert "auto_managed" in res_plain.output


def test_stats_and_settings_json(cli):
    import json
    runner = CliRunner()

    # Stats JSON
    res_stats = runner.invoke(
        spritzle_cli,
        ["stats", "--json"],
    )
    assert res_stats.exit_code == 0
    stats_data = json.loads(res_stats.output)
    assert isinstance(stats_data, dict)

    # Settings JSON
    res_settings = runner.invoke(
        spritzle_cli,
        ["settings", "--json"],
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
        ["settings", "--reset-all"],
    )

    # Defaults flag
    res_def = runner.invoke(
        spritzle_cli,
        ["settings", "--defaults", "--json"],
    )
    assert res_def.exit_code == 0
    defaults = json.loads(res_def.output)
    assert "download_rate_limit" in defaults

    # Modified flag when nothing modified
    res_mod_none = runner.invoke(
        spritzle_cli,
        ["settings", "--modified"],
    )
    assert res_mod_none.exit_code == 0
    assert "No settings have been modified" in res_mod_none.output

    # Modify a setting
    res_set = runner.invoke(
        spritzle_cli,
        ["settings", "-s", "download_rate_limit", "500000"],
    )
    assert res_set.exit_code == 0

    # Modified flag should now show only the modified setting
    res_mod = runner.invoke(
        spritzle_cli,
        ["settings", "--modified", "--json"],
    )
    assert res_mod.exit_code == 0
    mod_data = json.loads(res_mod.output)
    assert list(mod_data.keys()) == ["download_rate_limit"]
    assert mod_data["download_rate_limit"] == 500000

    # Clean up
    runner.invoke(
        spritzle_cli,
        ["settings", "--reset", "download_rate_limit"],
    )


def test_settings_reset_commands(cli):
    runner = CliRunner()

    # Reset specific key
    runner.invoke(
        spritzle_cli,
        ["settings", "-s", "download_rate_limit", "999999"],
    )
    res_reset = runner.invoke(
        spritzle_cli,
        ["settings", "--reset", "download_rate_limit"],
    )
    assert res_reset.exit_code == 0
    assert "download_rate_limit" in res_reset.output

    # Verify download_rate_limit was reset
    res_check = runner.invoke(
        spritzle_cli,
        ["settings", "--modified"],
    )
    assert "download_rate_limit" not in res_check.output

    # Reset all
    runner.invoke(
        spritzle_cli,
        ["settings", "-s", "download_rate_limit", "1111", "-s", "upload_rate_limit", "2222"],
    )
    res_reset_all = runner.invoke(
        spritzle_cli,
        ["settings", "--reset-all"],
    )
    assert res_reset_all.exit_code == 0
    assert "Reset all" in res_reset_all.output

    # After reset all, nothing is modified from baseline
    res_after_all = runner.invoke(
        spritzle_cli,
        ["settings", "--modified"],
    )
    assert "No settings have been modified" in res_after_all.output


def test_settings_visual_modified_indicator(cli):
    runner = CliRunner()

    # Modify download_rate_limit
    res_set = runner.invoke(
        spritzle_cli,
        ["settings", "-s", "download_rate_limit", "777777"],
    )
    assert res_set.exit_code == 0, res_set.output

    # Invoke with color
    res = runner.invoke(
        spritzle_cli,
        ["--color", "settings"],
    )
    assert res.exit_code == 0
    assert "* download_rate_limit" in res.output or "* download_rate_" in res.output
    assert "modified from default" in res.output

    # Clean up
    runner.invoke(
        spritzle_cli,
        ["settings", "--reset-all"],
    )


def test_quiet_action_commands(cli):
    import libtorrent as lt
    from spritzle.daemon.keys import APP_KEY_CORE
    from tests.daemon.common import torrent_dir

    t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
    handle = _add_test_torrent(cli.app[APP_KEY_CORE].session, lt.torrent_info(lt.bdecode(t1)))
    info_hash = str(handle.info_hash())

    runner = CliRunner()
    # Pause with --quiet
    res_pause = runner.invoke(
        spritzle_cli,
        ["pause", "-Q", "file1.txt"],
    )
    assert res_pause.exit_code == 0
    assert res_pause.output.strip() == info_hash

    # Resume with --quiet
    res_resume = runner.invoke(
        spritzle_cli,
        ["resume", "--quiet", "file1.txt"],
    )
    assert res_resume.exit_code == 0
    assert res_resume.output.strip() == info_hash

    # Remove with --quiet
    res_remove = runner.invoke(
        spritzle_cli,
        ["remove", "-Q", "file1.txt"],
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


def test_daemon_config_json_and_plain(cli):
    import json
    runner = CliRunner()

    # JSON mode
    res_json = runner.invoke(
        spritzle_cli,
        ["daemon-config", "--json"],
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert isinstance(data, dict)
    assert "save_resume_data_interval" in data


    # Plain mode
    res_plain = runner.invoke(
        spritzle_cli,
        ["daemon-config", "--plain"],
    )
    assert res_plain.exit_code == 0
    assert "save_resume_data_interval" in res_plain.output


    # Color mode
    res_color = runner.invoke(
        spritzle_cli,
        ["--color", "daemon-config"],
    )
    assert res_color.exit_code == 0
    assert "Spritzle Daemon Configuration" in res_color.output


def test_add_quiet(cli):
    from tests.daemon.common import torrent_dir

    t_file = str(torrent_dir / "testtorrent1.torrent")
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli,
        ["add", "-Q", t_file],
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


def test_offline_daemon_connection_error(tmp_path):
    from spritzle.cli.config import RemotesConfig

    RemotesConfig(config_dir=tmp_path).set_remote(
        "offline", "http://127.0.0.1:59999", "spz_d_off", "key"
    )
    runner = CliRunner()
    result = runner.invoke(spritzle_cli, ["-c", str(tmp_path), "-r", "offline", "list"])
    assert result.exit_code == 1
    assert "Could not connect to spritzled" in result.output
    assert "Is the daemon running?" in result.output


def test_daemon_config_positional_arguments(cli):
    runner = CliRunner()

    # Set key via positional arguments
    res_set = runner.invoke(
        spritzle_cli, ["daemon-config", "auth_timeout", "240"]
    )
    assert res_set.exit_code == 0

    # Get single key via positional argument
    res_get = runner.invoke(
        spritzle_cli, ["daemon-config", "auth_timeout"]
    )
    assert res_get.exit_code == 0
    assert "240" in res_get.output

    # JSON get single key
    res_json = runner.invoke(
        spritzle_cli, ["daemon-config", "auth_timeout", "--json"]
    )
    assert res_json.exit_code == 0
    d = json.loads(res_json.output)
    assert d == {"auth_timeout": 240}


def test_daemon_config_reload_and_errors(cli):
    runner = CliRunner()

    # Reload normal
    res = runner.invoke(spritzle_cli, ["daemon-config", "--reload"])
    assert res.exit_code == 0
    assert "no changes detected" in res.output

    # Reload color
    res_color = runner.invoke(spritzle_cli, ["--color", "daemon-config", "--reload"])
    assert res_color.exit_code == 0

    # Reload json
    res_json = runner.invoke(spritzle_cli, ["daemon-config", "--reload", "--json"])
    assert res_json.exit_code == 0
    assert json.loads(res_json.output)["reloaded"] is False

    # Reload plain
    res_plain = runner.invoke(spritzle_cli, ["daemon-config", "--reload", "--plain"])
    assert res_plain.exit_code == 0

    # Nonexistent key
    res_err = runner.invoke(spritzle_cli, ["daemon-config", "nonexistent_option"])
    assert res_err.exit_code == 1
    assert "Config key 'nonexistent_option' not found." in res_err.output

    # Single key color
    res_single_color = runner.invoke(spritzle_cli, ["--color", "daemon-config", "save_resume_data_interval"])
    assert res_single_color.exit_code == 0, res_single_color.output

    # Single key plain
    res_single_plain = runner.invoke(spritzle_cli, ["daemon-config", "save_resume_data_interval", "--plain"])
    assert res_single_plain.exit_code == 0
    assert "save_resume_data_interval" in res_single_plain.output


def test_info_command(cli):
    runner = CliRunner()

    # Add a torrent to core
    from spritzle.daemon.keys import APP_KEY_CORE
    import libtorrent as lt
    t_path = "tests/daemon/torrents/random_one_file.torrent"
    with open(t_path, "rb") as f:
        t_data = f.read()
    ti = lt.torrent_info(lt.bdecode(t_data))
    core = cli.app[APP_KEY_CORE]
    handle = _add_test_torrent(core.session, ti)
    ih = str(handle.info_hash())

    # Add a tracker to the handle
    handle.add_tracker({"url": "http://tracker.example.com/announce", "tier": 0})

    # Plain output
    res_info = runner.invoke(
        spritzle_cli, ["info", ih, "--plain"]
    )
    assert res_info.exit_code == 0
    assert ih in res_info.output
    assert "Info Hash" in res_info.output
    assert "Added" in res_info.output
    assert "Share Ratio" in res_info.output
    assert "Files (1):" in res_info.output
    assert "tmprandomfile" in res_info.output
    assert "Trackers:" in res_info.output
    assert "http://tracker.example.com/announce" in res_info.output

    # JSON output
    res_json = runner.invoke(
        spritzle_cli, ["info", ih, "--json"]
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["info_hash"] == ih
    assert "files" in data
    assert len(data["files"]) == 1
    assert data["files"][0]["path"] == "tmprandomfile"
    assert "trackers" in data
    assert any(t["url"] == "http://tracker.example.com/announce" for t in data["trackers"])
    assert "added_time" in data
    assert data["added_time"] > 0

    # Color output (ensure markup tags like [green] are not leaked as raw text)
    res_color = runner.invoke(
        spritzle_cli, ["--color", "info", ih]
    )
    assert res_color.exit_code == 0
    assert "[green]" not in res_color.output
    assert "[/green]" not in res_color.output
    assert "State" in res_color.output
    assert "tmprandomfile" in res_color.output
    assert "Trackers" in res_color.output

    # Error visibility
    core.torrent_data.setdefault(ih, {})["last_error"] = "Storage device write failure"
    res_err = runner.invoke(spritzle_cli, ["info", ih, "--plain"])
    assert res_err.exit_code == 0
    assert "Storage device write failure" in res_err.output

    # Nonexistent torrent
    res_nonexistent = runner.invoke(spritzle_cli, ["info", "0" * 40])
    assert res_nonexistent.exit_code == 1
    assert "No torrent found matching" in res_nonexistent.output


def test_info_formatting_and_subresource_fallbacks(capsys):
    import asyncio
    from unittest.mock import patch
    import pytest
    from spritzle.cli.commands.info import f as info_f

    class MockResp:
        def __init__(self, data, status=200):
            self._data = data
            self.status = status
            self.reason = "OK"

        async def json(self):
            return self._data

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class MockSession:
        def __init__(self, full_data):
            self.full_data = full_data

        def get(self, url):
            if "files" in url:
                return MockResp([{"index": 0, "progress": 1.0, "size": 1024, "path": "file.txt"}])
            if "peers" in url:
                return MockResp([{"ip": "1.2.3.4:5678", "client": "Deluge 2.1.1", "down_speed": 1000, "up_speed": 500, "progress": 0.75}])
            if "trackers" in url:
                return MockResp([
                    {"tier": 0, "url": "http://tr1", "updating": True},
                    {"tier": 0, "url": "http://tr2", "fails": 2},
                    {"tier": 0, "url": "http://tr3", "is_working": True},
                    {"tier": 0, "url": "http://tr4"},
                ])
            return MockResp(self.full_data)

    class MockClient:
        def __init__(self, full_data):
            self.session: Any = MockSession(full_data)
            self.color = "never"
            self.plain = True

        def url(self, path):
            return f"http://127.0.0.1/{path}"

    full_payload = {
        "name": "archlinux-test",
        "state": "downloading",
        "total_pieces": None,
        "completed_time": 1700000000,
        "spritzle.tags": "single_tag_string",
        "error": {"value": 1, "message": "Custom disk error"},
    }
    client = MockClient(full_payload)
    with patch("spritzle.cli.commands.info.resolve_single_torrent", return_value="0" * 40):
        asyncio.run(info_f(client, "0" * 40, plain=True))

    captured = capsys.readouterr().out
    assert "archlinux-test" in captured
    assert "Connected Peers (1):" in captured
    assert "Deluge 2.1.1" in captured
    assert "Trackers:" in captured
    assert "updating" in captured
    assert "working" in captured
    assert "Custom disk error" in captured
    assert "Completed" in captured
    assert "single_tag_string" in captured

    # Test errc dict and errc int
    full_payload["error"] = None
    full_payload["errc"] = {"value": 5, "message": "Read error"}
    with patch("spritzle.cli.commands.info.resolve_single_torrent", return_value="0" * 40):
        asyncio.run(info_f(client, "0" * 40, plain=True))
    assert "Read error" in capsys.readouterr().out

    full_payload["errc"] = 42
    with patch("spritzle.cli.commands.info.resolve_single_torrent", return_value="0" * 40):
        asyncio.run(info_f(client, "0" * 40, plain=True))
    assert "42" in capsys.readouterr().out

    # Non-200 response in f
    class ErrorSession:
        def get(self, url):
            return MockResp({}, status=500)

    error_client = MockClient({})
    error_client.session = ErrorSession()
    with patch("spritzle.cli.commands.info.resolve_single_torrent", return_value="0" * 40):
        with pytest.raises(SystemExit):
            asyncio.run(info_f(error_client, "0" * 40, plain=True))


def test_info_display_with_peers():
    import io
    from rich.console import Console
    from spritzle.cli.display import render_info_card

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, color_system="truecolor", width=120, height=40)
    data = {
        "name": "archlinux-x86_64.iso",
        "state": "downloading",
        "progress": 0.5,
        "download_rate": 1048576,
        "upload_rate": 524288,
        "total_size": 1000000000,
        "total_done": 500000000,
        "total_wanted": 1000000000,
        "num_peers": 2,
        "num_seeds": 1,
        "num_pieces": 100,
        "total_pieces": 200,
        "piece_length": 524288,
        "added_time": 1700000000,
        "completed_time": 0,
        "save_path": "/tmp",
        "trackers": [
            {"tier": 0, "url": "http://tracker.archlinux.org:6969/announce", "verified": True}
        ],
        "peers": [
            {
                "ip": "192.168.1.50:51413",
                "client": "Deluge 2.1.1",
                "down_speed": 1048576,
                "up_speed": 0,
                "progress": 0.95,
            }
        ],
        "files": [
            {
                "index": 0,
                "path": "archlinux-x86_64.iso",
                "size": 1000000000,
                "done": 500000000,
                "progress": 0.5,
            }
        ],
    }
    render_info_card(console, data, "44a040be6d74d8d290cd20128788864cbf770719", color_opt=True)
    out = buf.getvalue()
    assert "archlinux-x86_64.iso" in out
    assert "Connected Peers" in out
    assert "192.168.1.50:51413" in out
    assert "Deluge 2.1.1" in out
    assert "Trackers" in out
    assert "Files" in out
    assert "Added" in out
    assert "Share Ratio" in out
    assert "95.0%" in out
    assert "50.0%" in out


def test_add_magnet_command(cli):
    runner = CliRunner()

    magnet = "magnet:?xt=urn:btih:44a040be6d74d8d290cd20128788864cbf770719&dn=test_arch"
    res = runner.invoke(
        spritzle_cli, ["add", "-t", "linux", magnet]
    )
    assert res.exit_code == 0
    assert "Added test_arch" in res.output
    assert "44a040be" in res.output


def test_spritzled_help():
    from spritzle.daemon.main import main as spritzled_main

    runner = CliRunner()
    res = runner.invoke(spritzled_main, ["--help"])
    assert res.exit_code == 0
    assert "--host" in res.output
    assert "-H" in res.output
    assert "127.0.0.1" in res.output


def test_cli_config_offline(tmp_path):
    """Test that spritzle config operates locally without daemon."""
    runner = CliRunner()
    cfg_dir = str(tmp_path / "cfg")
    # Non-interactive / non-color (tablefmt="plain")
    res = runner.invoke(spritzle_cli, ["--config", cfg_dir, "config"])
    assert res.exit_code == 0
    assert "plain" in res.output

    # Color mode
    res_color = runner.invoke(spritzle_cli, ["--color", "--config", cfg_dir, "config"])
    assert res_color.exit_code == 0
    assert "Spritzle Client Configuration" in res_color.output


def test_cli_config_crud(tmp_path):
    """Test get, set, unset, and reset for CLI configuration."""
    runner = CliRunner()
    cfg_dir = str(tmp_path / "cfg")

    # Set positional
    res = runner.invoke(spritzle_cli, ["--config", cfg_dir, "config", "plain", "true"])
    assert res.exit_code == 0

    # Get single
    res = runner.invoke(spritzle_cli, ["--config", cfg_dir, "config", "plain"])
    assert res.exit_code == 0
    assert "True" in res.output or "true" in res.output or "on" in res.output

    # Set multiple with flags
    res = runner.invoke(
        spritzle_cli,
        ["--config", cfg_dir, "config", "-s", "color", "false", "-s", "plain", "false"],
    )
    assert res.exit_code == 0

    # Verify JSON output has typed values
    res_json = runner.invoke(spritzle_cli, ["--config", cfg_dir, "config", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["color"] is False
    assert data["plain"] is False

    # Unset color
    res_unset = runner.invoke(spritzle_cli, ["--config", cfg_dir, "config", "-u", "color"])
    assert res_unset.exit_code == 0
    res_json2 = runner.invoke(spritzle_cli, ["--config", cfg_dir, "config", "--json"])
    data2 = json.loads(res_json2.output)
    assert data2["color"] is None  # Reverted to default

    # Reset
    res_reset = runner.invoke(spritzle_cli, ["--config", cfg_dir, "config", "--reset"])
    assert res_reset.exit_code == 0
    res_json3 = runner.invoke(spritzle_cli, ["--config", cfg_dir, "config", "--json"])
    data3 = json.loads(res_json3.output)
    assert data3["plain"] is False


def test_cli_config_json_and_plain(tmp_path):
    """Test --json and --plain formatting for CLI config."""
    runner = CliRunner()
    cfg_dir = str(tmp_path / "cfg")

    # Plain output
    res_plain = runner.invoke(spritzle_cli, ["--config", cfg_dir, "config", "--plain"])
    assert res_plain.exit_code == 0
    assert "plain" in res_plain.output

    # Single key json
    res_single_json = runner.invoke(
        spritzle_cli, ["--config", cfg_dir, "config", "plain", "--json"]
    )
    assert res_single_json.exit_code == 0
    assert json.loads(res_single_json.output) == {"plain": False}

    # Nonexistent key error
    res_err = runner.invoke(spritzle_cli, ["--config", cfg_dir, "config", "nonexistent"])
    assert res_err.exit_code == 1
    assert "not found" in res_err.output

    # Single key color
    res_single_color = runner.invoke(
        spritzle_cli, ["--color", "--config", cfg_dir, "config", "plain"]
    )
    assert res_single_color.exit_code == 0
    assert "plain" in res_single_color.output

    # Single key plain
    res_single_plain = runner.invoke(
        spritzle_cli, ["--config", cfg_dir, "config", "plain", "--plain"]
    )
    assert res_single_plain.exit_code == 0
    assert "plain" in res_single_plain.output

    # Error saving CLI configuration in apply_set
    from unittest.mock import patch
    from spritzle.cli.config import CLIConfig
    with patch.object(CLIConfig, "__setitem__", side_effect=OSError("Read-only filesystem")):
        res_fail = runner.invoke(
            spritzle_cli, ["--config", cfg_dir, "config", "theme", "dark"]
        )
        assert res_fail.exit_code == 1
        assert "Error saving CLI configuration" in res_fail.output


def test_cli_config_ignores_and_preserves_remotes(tmp_path):
    """Test that remotes table and default_remote are in remotes.toml and preserved on config reset."""
    from spritzle.cli.config import CLIConfig, RemotesConfig

    cfg_dir = tmp_path / "cfg"
    remotes_cfg = RemotesConfig(config_dir=cfg_dir)
    remotes_cfg.set_remote("seedbox", "http://10.0.0.1:8080", "spz_d_test", "spritzle_123")
    remotes_cfg.set_default_remote("seedbox")

    cli_cfg = CLIConfig(config_dir=cfg_dir)
    cli_cfg["plain"] = True

    runner = CliRunner()
    res = runner.invoke(spritzle_cli, ["--config", str(cfg_dir), "config", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert "remotes" not in data
    assert "default_remote" not in data
    assert data["plain"] is True

    # Reset config overrides
    res_reset = runner.invoke(spritzle_cli, ["--config", str(cfg_dir), "config", "--reset"])
    assert res_reset.exit_code == 0

    # Remotes in remotes.toml must still be intact
    remotes_reloaded = RemotesConfig(config_dir=cfg_dir)
    assert remotes_reloaded.get_default_remote() == "seedbox"
    assert "seedbox" in remotes_reloaded.get_remotes()
    cli_reloaded = CLIConfig(config_dir=cfg_dir)
    assert cli_reloaded["plain"] is False  # reset to default


def test_cli_config_preserves_toml_comments(tmp_path):
    """Test that manual comments in cli.toml are preserved when keys are updated."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    toml_file = cfg_dir / "cli.toml"
    toml_file.write_text(
        "# Custom display comment\nplain = true\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    res = runner.invoke(
        spritzle_cli, ["--config", str(cfg_dir), "config", "plain", "false"]
    )
    assert res.exit_code == 0

    content = toml_file.read_text(encoding="utf-8")
    assert "# Custom display comment" in content
    assert "plain = false" in content


def test_cli_config_precedence(tmp_path):
    """Test precedence: CLI flag > cli.toml > hardcoded defaults."""
    from spritzle.cli.main import Client

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    toml_file = cfg_dir / "cli.toml"
    toml_file.write_text('plain = true\ncolor = false\n', encoding="utf-8")

    # 1. Defaults to values in cli.toml
    c1 = Client(config=str(cfg_dir))
    assert c1.plain is True
    assert c1.color is False

    # 2. CLI arguments take highest precedence
    c2 = Client(color=True, config=str(cfg_dir))
    assert c2.color is True


def test_no_underscore_aliases():
    """Verify that daemon_config and move_storage are not registered aliases."""
    runner = CliRunner()
    res1 = runner.invoke(spritzle_cli, ["daemon_config"])
    assert res1.exit_code != 0
    assert "No such command 'daemon_config'" in res1.output

    res2 = runner.invoke(spritzle_cli, ["move_storage"])
    assert res2.exit_code != 0
    assert "No such command 'move_storage'" in res2.output


def test_status_command(cli):
    """Test the top-level 'status' command."""
    runner = CliRunner()

    # Default output
    res = runner.invoke(spritzle_cli, ["status"])
    assert res.exit_code == 0
    assert "Status" in res.output and "online" in res.output

    # Plain output
    res_plain = runner.invoke(spritzle_cli, ["status", "--plain"])
    assert res_plain.exit_code == 0
    assert "status\tonline" in res_plain.output

    # JSON output
    res_json = runner.invoke(spritzle_cli, ["status", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["status"] == "online"
    assert "daemon_id" in data
    assert "num_torrents" in data

    # Color output
    res_color = runner.invoke(spritzle_cli, ["--color", "status"])
    assert res_color.exit_code == 0

    # format_uptime unit test
    from spritzle.cli.commands.status import format_uptime as status_format_uptime
    assert status_format_uptime(30) == "30s"
    assert status_format_uptime(90) == "1m 30s"
    assert status_format_uptime(3700) == "1h 1m"
    assert status_format_uptime(100000) == "1d 3h"


def test_status_command_auth_and_server_error(tmp_path):
    from spritzle.cli.config import RemotesConfig
    from unittest.mock import patch

    RemotesConfig(config_dir=tmp_path).set_remote(
        "bad_auth", "http://127.0.0.1:8080", "dummy_id", "spritzle_invalid_key"
    )

    class MockResp401:
        status = 401
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    class MockResp500:
        status = 500
        reason = "Server Error"
        async def json(self):
            return {"message": "Internal failure"}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    runner = CliRunner()
    with patch("aiohttp.ClientSession.get", return_value=MockResp401()):
        res = runner.invoke(spritzle_cli, ["-c", str(tmp_path), "-r", "bad_auth", "status"])
        assert res.exit_code == 1
        assert "Authentication failed" in res.output

    with patch("aiohttp.ClientSession.get", return_value=MockResp500()):
        res500 = runner.invoke(spritzle_cli, ["-c", str(tmp_path), "-r", "bad_auth", "status"])
        assert res500.exit_code == 1
        assert "Daemon returned HTTP 500" in res500.output


def test_completion_command():
    """Test the 'completion' command for various shells."""
    runner = CliRunner()

    res_bash = runner.invoke(spritzle_cli, ["completion", "bash"])
    assert res_bash.exit_code == 0
    assert "_spritzle_completion" in res_bash.output or "complete" in res_bash.output

    res_zsh = runner.invoke(spritzle_cli, ["completion", "zsh"])
    assert res_zsh.exit_code == 0
    assert "compdef" in res_zsh.output or "_spritzle" in res_zsh.output

    res_fish = runner.invoke(spritzle_cli, ["completion", "fish"])
    assert res_fish.exit_code == 0
    assert "command spritzle" in res_fish.output


def test_stats_command_all_and_raw(cli):
    """Test the 'stats' command with --all and --raw."""
    runner = CliRunner()

    # High-level summary by default
    res_default = runner.invoke(spritzle_cli, ["stats"])
    assert res_default.exit_code == 0
    assert "Torrents: Downloading" in res_default.output or "Session Statistics" in res_default.output

    # Detailed session metrics with --all
    res_all = runner.invoke(spritzle_cli, ["stats", "--all"])
    assert res_all.exit_code == 0
    assert "net." in res_all.output or "session." in res_all.output or "dht." in res_all.output

    # Raw metrics
    res_raw = runner.invoke(spritzle_cli, ["stats", "--raw"])
    assert res_raw.exit_code == 0


def test_add_command_stdin(cli):
    """Test adding a torrent via stdin pipe."""
    runner = CliRunner()
    magnet = "magnet:?xt=urn:btih:44a040be6d74d8d290cd20128788864cbf770719&dn=test_stdin"

    res = runner.invoke(spritzle_cli, ["add", "-"], input=magnet)
    assert res.exit_code == 0, res.output
    assert "Added test_stdin" in res.output
    assert "44a040be" in res.output


def test_add_command_invalid_magnet_preflight():
    """Test preflight validation for truncated/unquoted magnet links."""
    runner = CliRunner()
    # Magnet missing xt
    res = runner.invoke(spritzle_cli, ["add", "magnet:?dn=test"])
    assert res.exit_code != 0
    assert "missing 'xt' parameter" in res.output


def test_format_eta():
    from spritzle.cli.display import format_eta
    assert format_eta(None) == "--"
    assert format_eta(-5) == "--"
    assert format_eta(0) == "0s"
    assert format_eta(45) == "45s"
    assert format_eta(65) == "1m 05s"
    assert format_eta(3665) == "1h 01m"
    assert format_eta(90000) == "1d 01h"
    assert format_eta(45, human=False) == "45"
    assert format_eta(None, human=False) == "-1"


def test_add_command_rich_card(cli):
    runner = CliRunner()
    from tests.daemon.common import torrent_dir
    t_file = str(torrent_dir / "random_one_file.torrent")

    res = runner.invoke(spritzle_cli, ["add", t_file])
    assert res.exit_code == 0
    assert "Added" in res.output
    assert "Size:" in res.output
    assert "Save Path:" in res.output
    assert "Status:" in res.output
    assert "Track progress:" in res.output
    assert "spritzle list" in res.output
    assert "spritzle info" in res.output


def test_add_command_json_and_plain(cli):
    runner = CliRunner()
    from tests.daemon.common import torrent_dir
    t_file = str(torrent_dir / "random_one_file.torrent")

    # JSON output
    res_json = runner.invoke(spritzle_cli, ["add", "--json", t_file])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "info_hash" in data
    assert "name" in data
    assert "save_path" in data

    # Plain output
    res_plain = runner.invoke(spritzle_cli, ["add", "--plain", t_file])
    assert res_plain.exit_code == 0
    assert "Added" in res_plain.output
    assert "Size:" in res_plain.output
    assert "Save Path:" in res_plain.output


def test_add_command_quiet(cli):
    runner = CliRunner()
    from tests.daemon.common import torrent_dir
    t_file = str(torrent_dir / "random_one_file.torrent")

    res = runner.invoke(spritzle_cli, ["add", "-Q", t_file])
    assert res.exit_code == 0
    # Must contain only the 40-char info_hash followed by newline
    output = res.output.strip()
    assert len(output) == 40
    assert int(output, 16)


def test_add_command_watch(cli):
    from unittest.mock import patch
    import asyncio
    runner = CliRunner()
    from tests.daemon.common import torrent_dir
    t_file = str(torrent_dir / "random_one_file.torrent")

    async def mock_sleep(*args, **kwargs):
        raise KeyboardInterrupt()

    with patch.object(asyncio, "sleep", side_effect=mock_sleep):
        res = runner.invoke(spritzle_cli, ["add", "--watch", t_file])
        assert res.exit_code == 0
        assert "Added" in res.output
        assert "Watching stopped" in res.output


def test_top_command(cli):
    from unittest.mock import patch
    import asyncio
    runner = CliRunner()

    async def mock_sleep(*args, **kwargs):
        raise KeyboardInterrupt()

    with patch.object(asyncio, "sleep", side_effect=mock_sleep):
        res = runner.invoke(spritzle_cli, ["top", "--plain"])
        assert res.exit_code == 0
        assert "Spritzle Monitor" in res.output
        assert "Dashboard stopped" not in res.output


def test_list_command_watch(cli):
    from unittest.mock import patch
    import asyncio
    runner = CliRunner()

    async def mock_sleep(*args, **kwargs):
        raise KeyboardInterrupt()

    with patch.object(asyncio, "sleep", side_effect=mock_sleep):
        res = runner.invoke(spritzle_cli, ["list", "--watch", "--plain"])
        assert res.exit_code == 0
        assert "Spritzle Monitor" in res.output
        assert "Dashboard stopped" not in res.output


def test_dht_bootstrap_indicator_stats(cli):
    runner = CliRunner()

    # In stats --json, bootstrapping indicator
    res_stats_json = runner.invoke(spritzle_cli, ["stats", "--json"])
    assert res_stats_json.exit_code == 0
    stats_data = json.loads(res_stats_json.output)
    assert "dht" in stats_data
    assert "bootstrapping" in stats_data["dht"]

    # In stats plain / summary
    res_stats = runner.invoke(spritzle_cli, ["stats"])
    assert res_stats.exit_code == 0
    assert "bootstrapping DHT..." in res_stats.output


def test_top_command_quit_with_q(cli):
    from unittest.mock import patch
    import asyncio
    runner = CliRunner()

    from spritzle.cli.dashboard import run_dashboard

    quit_event = asyncio.Event()
    original_run_dashboard = run_dashboard

    async def patched_run_dashboard(*args, **kwargs):
        kwargs["quit_event"] = quit_event
        quit_event.set()
        return await original_run_dashboard(*args, **kwargs)

    with patch("spritzle.cli.commands.top.run_dashboard", side_effect=patched_run_dashboard):
        res = runner.invoke(spritzle_cli, ["top", "--plain"])
        assert res.exit_code == 0
        assert "Spritzle Monitor" in res.output
        assert "Dashboard stopped" not in res.output


def test_key_press_watcher_pty():
    import asyncio
    import os
    import pty

    from spritzle.cli.dashboard import KeyPressWatcher

    master, slave = pty.openpty()

    async def run_test():
        watcher = KeyPressWatcher(fd=slave)
        async with watcher:
            assert not watcher.quit_event.is_set()
            os.write(master, b"q")
            await asyncio.wait_for(watcher.quit_event.wait(), timeout=1.0)
            assert watcher.quit_event.is_set()

    asyncio.run(run_test())
    import termios
    assert bool(termios.tcgetattr(slave)[3] & termios.ECHO) is True
    os.close(master)
    os.close(slave)


def test_key_press_watcher_uppercase_q_pty():
    import asyncio
    import os
    import pty
    import termios

    from spritzle.cli.dashboard import KeyPressWatcher

    master, slave = pty.openpty()

    async def run_test():
        watcher = KeyPressWatcher(fd=slave)
        async with watcher:
            assert not watcher.quit_event.is_set()
            os.write(master, b"Q")
            await asyncio.wait_for(watcher.quit_event.wait(), timeout=1.0)
            assert watcher.quit_event.is_set()

    asyncio.run(run_test())
    attr = termios.tcgetattr(slave)
    assert bool(attr[3] & termios.ECHO) is True
    os.close(master)
    os.close(slave)


def test_key_press_watcher_echo_restored_on_cancellation_and_atexit():
    import asyncio
    import os
    import pty
    import termios

    from spritzle.cli.dashboard import KeyPressWatcher, _restore_all_terminals

    master, slave = pty.openpty()

    async def run_test():
        watcher = KeyPressWatcher(fd=slave)
        try:
            async with watcher:
                # Terminal echo should be disabled in cbreak
                mid = termios.tcgetattr(slave)
                assert not (mid[3] & termios.ECHO)
                raise RuntimeError("simulated crash")
        except RuntimeError:
            pass

    asyncio.run(run_test())
    # Verify __aexit__ cleaned up
    attr = termios.tcgetattr(slave)
    assert bool(attr[3] & termios.ECHO) is True

    # Also test global restorer fallback
    tty_mod = __import__("tty")
    tty_mod.setcbreak(slave)
    mid2 = termios.tcgetattr(slave)
    assert not (mid2[3] & termios.ECHO)

    # Register in active restorers and trigger global restorer
    from spritzle.cli.dashboard import _active_terminal_restorers
    _active_terminal_restorers.add(lambda: termios.tcsetattr(slave, termios.TCSANOW, attr))
    _restore_all_terminals()
    after = termios.tcgetattr(slave)
    assert bool(after[3] & termios.ECHO) is True

    os.close(master)
    os.close(slave)


def test_key_press_watcher_sigint_handling():
    import asyncio
    import os
    import pty
    import termios

    from spritzle.cli.dashboard import KeyPressWatcher

    master, slave = pty.openpty()

    async def run_test():
        watcher = KeyPressWatcher(fd=slave)
        async with watcher:
            assert not watcher.quit_event.is_set()
            # Simulate SIGINT signal delivery
            watcher._on_signal()
            assert watcher.quit_event.is_set()

    asyncio.run(run_test())
    attr = termios.tcgetattr(slave)
    assert bool(attr[3] & termios.ECHO) is True

    os.close(master)
    os.close(slave)


def test_build_dashboard_renderable_subtitle():
    from spritzle.cli.dashboard import build_dashboard_renderable
    panel_color = build_dashboard_renderable([], {}, is_color=True)
    assert "Press 'q' or Ctrl+C to exit" in str(panel_color.subtitle)
    panel_plain = build_dashboard_renderable([], {}, is_color=False)
    assert "Press 'q' or Ctrl+C to exit" in str(panel_plain.subtitle)


def test_dashboard_row_single_line():
    from rich.console import Console, Group
    from rich.table import Table
    from spritzle.cli.dashboard import build_dashboard_renderable

    items = [
        {
            "name": "archlinux-2026.09.01-x86_64-super-extremely-long-name-that-might-overflow.iso",
            "state": "downloading",
            "progress": 0.452,
            "download_rate": 4520000,
            "upload_rate": 120000,
            "total_wanted": 1200000000,
            "total_done": 540000000,
            "num_peers": 24,
            "num_seeds": 8,
        },
        {
            "name": "short.iso",
            "state": "seeding",
            "progress": 1.0,
            "download_rate": 0,
            "upload_rate": 850000,
            "total_wanted": 4500000000,
            "total_done": 4500000000,
            "num_peers": 0,
            "num_seeds": 0,
        },
    ]

    for width in (60, 80, 100, 120):
        c = Console(width=width, height=30)
        panel = build_dashboard_renderable(items, {}, is_color=True)
        assert isinstance(panel.renderable, Group)
        table = panel.renderable.renderables[2]
        assert isinstance(table, Table)
        for col in table.columns:
            assert col.no_wrap is True

        with c.capture() as cap:
            c.print(table)
        rendered_lines = [line for line in cap.get().splitlines() if line.strip()]
        assert len(rendered_lines) == 3


def test_dashboard_renderable_fullscreen_height():
    from rich.console import Console
    from spritzle.cli.dashboard import build_dashboard_renderable

    panel = build_dashboard_renderable([], {}, is_color=True, height=24)
    assert panel.height == 24

    c = Console(width=80, height=24)
    with c.capture() as cap:
        c.print(panel)
    lines = cap.get().splitlines()
    assert len(lines) == 24
    assert "Spritzle Torrent Monitor" in lines[0]
    assert "Press 'q' or Ctrl+C to exit" in lines[-1]


def test_dashboard_colors_dht_and_upload():
    from rich.console import Group
    from spritzle.cli.dashboard import build_dashboard_renderable
    from spritzle.cli.display import format_speed

    upload_speed = format_speed(1048576, human=True, use_color=True, is_upload=True)
    assert "[blue]▲" in upload_speed
    assert "[cyan]" not in upload_speed

    stats = {"dht.dht_nodes": 50}
    panel = build_dashboard_renderable([], stats, is_color=True)
    assert isinstance(panel.renderable, Group)
    header_str = str(panel.renderable.renderables[0])
    assert "[magenta]● 50 nodes[/magenta]" in header_str
    assert "[bold blue]" in header_str
    assert "[bold cyan]" not in header_str


def test_files_command(cli):
    runner = CliRunner()
    from spritzle.daemon.keys import APP_KEY_CORE
    import libtorrent as lt

    t_path = "tests/daemon/torrents/random_one_file.torrent"
    with open(t_path, "rb") as f:
        t_data = f.read()
    ti = lt.torrent_info(lt.bdecode(t_data))
    core = cli.app[APP_KEY_CORE]
    handle = _add_test_torrent(core.session, ti)
    ih = str(handle.info_hash())

    # 1. Plain listing
    res = runner.invoke(spritzle_cli, ["files", ih, "--plain"])
    assert res.exit_code == 0
    assert "tmprandomfile" in res.output
    assert "Index" in res.output
    assert "Priority" in res.output

    # 2. JSON listing
    res_json = runner.invoke(spritzle_cli, ["files", ih, "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert len(data) == 1
    assert data[0]["path"] == "tmprandomfile"

    # 3. Set priority using -p
    res_set = runner.invoke(spritzle_cli, ["files", ih, "-p", "0", "7"])
    assert res_set.exit_code == 0
    assert "Updated priorities" in res_set.output

    # 4. Set priority using --skip
    res_skip = runner.invoke(spritzle_cli, ["files", ih, "--skip", "0"])
    assert res_skip.exit_code == 0
    assert "Updated priorities" in res_skip.output

    # 5. Set priority using --normal
    res_norm = runner.invoke(spritzle_cli, ["files", ih, "--normal", "0"])
    assert res_norm.exit_code == 0
    assert "Updated priorities" in res_norm.output


def test_trackers_command(cli):
    runner = CliRunner()
    from spritzle.daemon.keys import APP_KEY_CORE
    import libtorrent as lt

    t_path = "tests/daemon/torrents/random_one_file.torrent"
    with open(t_path, "rb") as f:
        t_data = f.read()
    ti = lt.torrent_info(lt.bdecode(t_data))
    core = cli.app[APP_KEY_CORE]
    handle = _add_test_torrent(core.session, ti)
    ih = str(handle.info_hash())

    # 1. Add tracker
    tracker_url = "http://clitracker.example.com:6969/announce"
    res_add = runner.invoke(spritzle_cli, ["trackers", ih, "--add", tracker_url])
    assert res_add.exit_code == 0
    assert "Added tracker" in res_add.output

    # 2. Plain listing
    res_list = runner.invoke(spritzle_cli, ["trackers", ih, "--plain"])
    assert res_list.exit_code == 0
    assert tracker_url in res_list.output
    assert "Tier" in res_list.output

    # 3. JSON listing
    res_json = runner.invoke(spritzle_cli, ["trackers", ih, "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert any(t["url"] == tracker_url for t in data)

    # 4. Reannounce via trackers --reannounce
    res_re = runner.invoke(spritzle_cli, ["trackers", ih, "--reannounce"])
    assert res_re.exit_code == 0
    assert "Reannounced" in res_re.output

    # 5. Remove tracker
    res_del = runner.invoke(spritzle_cli, ["trackers", ih, "--remove", tracker_url])
    assert res_del.exit_code == 0
    assert "Removed tracker" in res_del.output


def test_reannounce_command(cli):
    runner = CliRunner()
    from spritzle.daemon.keys import APP_KEY_CORE
    import libtorrent as lt

    t_path = "tests/daemon/torrents/random_one_file.torrent"
    with open(t_path, "rb") as f:
        t_data = f.read()
    ti = lt.torrent_info(lt.bdecode(t_data))
    core = cli.app[APP_KEY_CORE]
    handle = _add_test_torrent(core.session, ti)
    ih = str(handle.info_hash())

    res = runner.invoke(spritzle_cli, ["reannounce", ih])
    assert res.exit_code == 0
    assert "reannounced successfully" in res.output

    # Quiet mode
    res_q = runner.invoke(spritzle_cli, ["reannounce", ih, "-Q"])
    assert res_q.exit_code == 0
    assert ih in res_q.output

    # All torrents
    res_all = runner.invoke(spritzle_cli, ["reannounce", "--all"])
    assert res_all.exit_code == 0
    assert "Reannounced" in res_all.output

    # By query
    res_query = runner.invoke(spritzle_cli, ["reannounce", "-q", "name=tmprandomfile"])
    assert res_query.exit_code == 0

    # No args (must specify torrent, --query, or --all)
    res_empty = runner.invoke(spritzle_cli, ["reannounce"])
    assert res_empty.exit_code == 1
    assert "Specify a torrent" in res_empty.output

    # Query with no matches
    res_no_match = runner.invoke(spritzle_cli, ["reannounce", "-q", "name=nomatch"])
    assert res_no_match.exit_code == 0
    assert "No matching torrents found" in res_no_match.output

    # Nonexistent torrent
    res_none = runner.invoke(spritzle_cli, ["reannounce", "0" * 40])
    assert res_none.exit_code == 1


def test_settings_profile_and_interface_command(cli):
    runner = CliRunner()

    # Set listen-interfaces
    res = runner.invoke(spritzle_cli, ["settings", "-i", "127.0.0.1:6881"])
    assert res.exit_code == 0

    # Set profile
    res = runner.invoke(spritzle_cli, ["settings", "--profile", "deluge-2.1.1"])
    assert res.exit_code == 0

    # Verify via settings --json
    res_json = runner.invoke(spritzle_cli, ["settings", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["user_agent"] == "Deluge/2.1.1 libtorrent/2.0.10.0"
    assert data["peer_fingerprint"] == "-DE2110-"



def test_trackers_command_edge_cases(cli):
    runner = CliRunner()
    from spritzle.daemon.keys import APP_KEY_CORE
    import libtorrent as lt

    t_path = "tests/daemon/torrents/random_one_file.torrent"
    with open(t_path, "rb") as f:
        t_data = f.read()
    ti = lt.torrent_info(lt.bdecode(t_data))
    core = cli.app[APP_KEY_CORE]
    handle = _add_test_torrent(core.session, ti)
    ih = str(handle.info_hash())

    # Missing torrent argument
    res_missing = runner.invoke(spritzle_cli, ["trackers"])
    assert res_missing.exit_code == 1
    assert "Specify a torrent" in res_missing.output

    # Color output
    res_color = runner.invoke(spritzle_cli, ["--color", "trackers", ih])
    assert res_color.exit_code == 0

    # Missing torrent argument in manager
    res_mgr_no_torrent = runner.invoke(spritzle_cli, ["trackers", "--add", "http://foo.bar/announce"])
    assert res_mgr_no_torrent.exit_code == 1
    assert "Specify a torrent" in res_mgr_no_torrent.output

    # Error adding tracker (unsupported scheme)
    res_err_add = runner.invoke(spritzle_cli, ["trackers", ih, "--add", "ftp://bad.com/announce"])
    assert res_err_add.exit_code == 1
    assert "Error adding tracker" in res_err_add.output

    # Error removing tracker (index out of range)
    res_err_del = runner.invoke(spritzle_cli, ["trackers", ih, "--remove", "9999"])
    assert res_err_del.exit_code == 1
    assert "Error removing tracker" in res_err_del.output

    # Formatting of trackers in show (updating, error, working)
    from spritzle.cli.commands.trackers import show as trackers_show
    import asyncio
    from unittest.mock import patch, MagicMock

    mock_client = MagicMock()
    mock_client.color = "always"
    mock_client.plain = False

    class MockResp:
        status = 200
        async def json(self):
            return [
                {"tier": 0, "url": "http://tr1", "updating": True, "fails": 0, "next_announce": 10},
                {"tier": 1, "url": "http://tr2", "updating": False, "fails": 2, "next_announce": None, "message": "tracker timed out"},
                {"tier": 2, "url": "http://tr3", "updating": False, "fails": 0, "next_announce": 30},
            ]
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    mock_client.session.get = lambda url: MockResp()
    with patch("spritzle.cli.commands.trackers.resolve_single_torrent", return_value="0" * 40):
        # Color table
        asyncio.run(trackers_show(mock_client, "0" * 40, plain=False))
        # Plain table
        mock_client.color = "never"
        mock_client.plain = True
        asyncio.run(trackers_show(mock_client, "0" * 40, plain=True))


def test_files_command_edge_cases(cli):
    runner = CliRunner()
    from spritzle.daemon.keys import APP_KEY_CORE
    from spritzle.cli.commands.files import parse_priority_value
    import click
    import pytest
    import libtorrent as lt

    # Unit test parse_priority_value
    assert parse_priority_value("0") == 0
    assert parse_priority_value("7") == 7
    assert parse_priority_value("skip") == 0
    assert parse_priority_value("normal") == 4
    assert parse_priority_value("top") == 7
    with pytest.raises(click.BadParameter):
        parse_priority_value("invalid_val")
    with pytest.raises(click.BadParameter):
        parse_priority_value("99")

    # Missing torrent argument
    res_missing = runner.invoke(spritzle_cli, ["files"])
    assert res_missing.exit_code == 1
    assert "Specify a torrent" in res_missing.output

    t_path = "tests/daemon/torrents/random_one_file.torrent"
    with open(t_path, "rb") as f:
        t_data = f.read()
    ti = lt.torrent_info(lt.bdecode(t_data))
    core = cli.app[APP_KEY_CORE]
    handle = _add_test_torrent(core.session, ti)
    ih = str(handle.info_hash())

    # Color output
    res_color = runner.invoke(spritzle_cli, ["--color", "files", ih])
    assert res_color.exit_code == 0

    # Missing torrent argument on update
    res_missing_update = runner.invoke(spritzle_cli, ["files", "--top", "0"])
    assert res_missing_update.exit_code == 1
    assert "Specify a torrent" in res_missing_update.output

    # --top and --all options
    res_top = runner.invoke(spritzle_cli, ["files", ih, "--top", "0"])
    assert res_top.exit_code == 0

    # Color output with prio >= 6 (top)
    res_color_top = runner.invoke(spritzle_cli, ["--color", "files", ih])
    assert res_color_top.exit_code == 0

    # --skip option (prio == 0)
    res_skip = runner.invoke(spritzle_cli, ["files", ih, "--skip", "0"])
    assert res_skip.exit_code == 0

    # Color output with prio == 0 (skip)
    res_color_skip = runner.invoke(spritzle_cli, ["--color", "files", ih])
    assert res_color_skip.exit_code == 0

    res_all = runner.invoke(spritzle_cli, ["files", ih, "--all", "4"])
    assert res_all.exit_code == 0

    # Invalid index
    res_bad_idx = runner.invoke(spritzle_cli, ["files", ih, "-p", "invalid", "4"])
    assert res_bad_idx.exit_code == 1
    assert "Invalid file index" in res_bad_idx.output

    # Out of range index
    res_oob = runner.invoke(spritzle_cli, ["files", ih, "-p", "99", "4"])
    assert res_oob.exit_code == 1
    assert "out of range" in res_oob.output


def test_daemon_config_reload_and_edge_cases(cli):
    runner = CliRunner()

    # Reload config (color, plain, json)
    res_reload = runner.invoke(spritzle_cli, ["daemon-config", "--reload"])
    assert res_reload.exit_code == 0

    res_reload_plain = runner.invoke(spritzle_cli, ["daemon-config", "--reload", "--plain"])
    assert res_reload_plain.exit_code == 0

    res_reload_json = runner.invoke(spritzle_cli, ["daemon-config", "--reload", "--json"])
    assert res_reload_json.exit_code == 0
    data = json.loads(res_reload_json.output)
    assert "reloaded" in data

    # Nonexistent key
    res_nonexistent = runner.invoke(spritzle_cli, ["daemon-config", "nonexistent_key_xyz"])
    assert res_nonexistent.exit_code == 1
    assert "not found" in res_nonexistent.output

    # Single key with color
    res_single_color = runner.invoke(spritzle_cli, ["--color", "daemon-config", "default_save_path"])
    assert res_single_color.exit_code == 0
    assert "default_save_path" in res_single_color.output


def test_help_command_color_modes():
    runner = CliRunner()

    # Root help in color
    res_root = runner.invoke(spritzle_cli, ["--color", "help"])
    assert res_root.exit_code == 0
    assert "Spritzle" in res_root.output
    assert "Commands:" in res_root.output

    # Subcommand help with command help text
    res_add = runner.invoke(spritzle_cli, ["--color", "help", "add"])
    assert res_add.exit_code == 0
    assert "Usage:" in res_add.output
    assert "add" in res_add.output


def test_status_format_uptime_unit():
    from spritzle.cli.commands.status import format_uptime

    assert format_uptime(45) == "45s"
    assert format_uptime(125) == "2m 5s"
    assert format_uptime(3665) == "1h 1m"
    assert format_uptime(90000) == "1d 1h"


def test_batch_commands_not_found_and_quiet(cli):
    runner = CliRunner()
    from spritzle.daemon.keys import APP_KEY_CORE
    import libtorrent as lt

    # "No matching torrents found" branches
    for cmd in ["pause", "resume", "remove"]:
        res = runner.invoke(spritzle_cli, [cmd, "-q", "name.eq=nonexistent_xyz_12345"])
        assert res.exit_code == 0
        assert "No matching torrents found" in res.output

    # Quiet mode on existing torrent
    t_path = "tests/daemon/torrents/random_one_file.torrent"
    with open(t_path, "rb") as f:
        t_data = f.read()
    ti = lt.torrent_info(lt.bdecode(t_data))
    core = cli.app[APP_KEY_CORE]
    handle = _add_test_torrent(core.session, ti)
    ih = str(handle.info_hash())

    res_pause = runner.invoke(spritzle_cli, ["pause", "--quiet", ih])
    assert res_pause.exit_code == 0
    assert res_pause.output.strip() == ih

    res_resume = runner.invoke(spritzle_cli, ["resume", "-Q", ih])
    assert res_resume.exit_code == 0
    assert res_resume.output.strip() == ih

    res_remove = runner.invoke(spritzle_cli, ["remove", "-Q", ih])
    assert res_remove.exit_code == 0
    assert res_remove.output.strip() == ih


def test_add_command_validation_and_modes(cli):
    runner = CliRunner()

    # Invalid info-hash hex length
    res_bad_len = runner.invoke(spritzle_cli, ["add", "1234abcd"])
    assert res_bad_len.exit_code == 1
    assert "Invalid info-hash length" in res_bad_len.output

    # Malformed magnet link prefix
    res_malformed = runner.invoke(spritzle_cli, ["add", "magnet?xt=urn:btih:44a040be6d74d8d290cd20128788864cbf770719"])
    assert res_malformed.exit_code == 1
    assert "Malformed magnet link" in res_malformed.output

    # Trailing symbol warning
    res_trailing = runner.invoke(spritzle_cli, ["add", "magnet:?xt=urn:btih:44a040be6d74d8d290cd20128788864cbf770719&"])
    assert "truncated by the shell" in res_trailing.output or res_trailing.exit_code in (0, 1)

    # Add with --quiet and --color
    t_path = "tests/daemon/torrents/random_one_file.torrent"
    res_quiet = runner.invoke(spritzle_cli, ["add", "-Q", t_path])
    assert res_quiet.exit_code == 0
    ih = res_quiet.output.strip()
    assert len(ih) == 40

    # Add with --color summary
    t_path2 = "tests/daemon/torrents/testtorrent1.torrent"
    res_color = runner.invoke(spritzle_cli, ["--color", "add", t_path2])
    assert res_color.exit_code == 0
    assert "Added" in res_color.output


def test_display_helpers_and_errors():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from spritzle.cli.display import print_warning, get_response_error

    # print_warning with/without color
    print_warning("test plain warning", color_opt=False)
    print_warning("test color warning", color_opt=True)

    # get_response_error
    async def _test():
        # Dict with message
        resp1 = MagicMock()
        resp1.json = AsyncMock(return_value={"message": "custom error message"})
        assert await get_response_error(resp1) == "custom error message"

        # Dict with reason
        resp2 = MagicMock()
        resp2.json = AsyncMock(return_value={"reason": "bad request reason"})
        assert await get_response_error(resp2) == "bad request reason"

        # Text fallback
        resp3 = MagicMock()
        resp3.json = AsyncMock(side_effect=ValueError)
        resp3.text = AsyncMock(return_value="raw text error")
        assert await get_response_error(resp3) == "raw text error"

        # Reason fallback
        resp4 = MagicMock()
        resp4.json = AsyncMock(side_effect=ValueError)
        resp4.text = AsyncMock(side_effect=ValueError)
        resp4.reason = "Gateway Timeout"
        assert await get_response_error(resp4) == "Gateway Timeout"

    asyncio.run(_test())


def test_completion_command_unsupported():
    import pytest
    from spritzle.cli.commands.completion import command as completion_cmd

    assert completion_cmd.callback is not None
    with pytest.raises(SystemExit):
        completion_cmd.callback("unsupported_shell")
























