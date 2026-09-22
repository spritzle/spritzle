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
    result = runner.invoke(
        spritzle_cli, ["stats"]
    )
    assert result.exit_code == 0
    print(result.output)


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
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
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
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
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
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
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
        handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
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
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
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
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
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
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": ti, "save_path": "/tmp"})
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
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t2)), "save_path": "/tmp"})

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
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t2)), "save_path": "/tmp"})

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
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t2)), "save_path": "/tmp"})

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
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t2)), "save_path": "/tmp"})

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
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})

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
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
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

    # Caption contrast & legibility (no dim in caption)
    buf.seek(0)
    buf.truncate(0)
    render_kv_table(c, [("download_rate_limit", 1048576)], modified_keys={"download_rate_limit"})
    out_kv = buf.getvalue()
    assert "modified from default" in out_kv
    assert "\x1b[3m" not in out_kv  # Ensure 'italic' (which renders as inverse video white bar in some terminals) is not used
    assert "\x1b[2m" not in out_kv  # Ensure 'dim' is not used

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
    assert "\x1b[2m" not in out_rich  # Ensure 'dim' is not used


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
    cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})

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
    handle = cli.app[APP_KEY_CORE].session.add_torrent({"ti": lt.torrent_info(lt.bdecode(t1)), "save_path": "/tmp"})
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
    handle = core.session.add_torrent({"ti": ti, "save_path": "/tmp"})
    ih = str(handle.info_hash())

    # Plain output
    res_info = runner.invoke(
        spritzle_cli, ["info", ih, "--plain"]
    )
    assert res_info.exit_code == 0
    assert ih in res_info.output
    assert "Info Hash" in res_info.output

    # JSON output
    res_json = runner.invoke(
        spritzle_cli, ["info", ih, "--json"]
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["info_hash"] == ih

    # Color output (ensure markup tags like [green] are not leaked as raw text)
    res_color = runner.invoke(
        spritzle_cli, ["--color", "info", ih]
    )
    assert res_color.exit_code == 0
    assert "[green]" not in res_color.output
    assert "[/green]" not in res_color.output
    assert "State" in res_color.output

    # Error visibility
    core.torrent_data.setdefault(ih, {})["last_error"] = "Storage device write failure"
    res_err = runner.invoke(spritzle_cli, ["info", ih, "--plain"])
    assert res_err.exit_code == 0
    assert "Storage device write failure" in res_err.output


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
    os.close(master)
    os.close(slave)


def test_key_press_watcher_uppercase_q_pty():
    import asyncio
    import os
    import pty

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
    os.close(master)
    os.close(slave)


def test_build_dashboard_renderable_subtitle():
    from spritzle.cli.dashboard import build_dashboard_renderable
    panel_color = build_dashboard_renderable([], {}, is_color=True)
    assert "Press 'q' or Ctrl+C to exit" in str(panel_color.subtitle)
    panel_plain = build_dashboard_renderable([], {}, is_color=False)
    assert "Press 'q' or Ctrl+C to exit" in str(panel_plain.subtitle)


def test_dashboard_row_single_line():
    from rich.console import Console
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
        table = panel.renderable.renderables[2]
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
    from spritzle.cli.dashboard import build_dashboard_renderable
    from spritzle.cli.display import format_speed

    upload_speed = format_speed(1048576, human=True, use_color=True, is_upload=True)
    assert "[blue]▲" in upload_speed
    assert "[cyan]" not in upload_speed

    stats = {"dht.dht_nodes": 50}
    panel = build_dashboard_renderable([], stats, is_color=True)
    header_str = str(panel.renderable.renderables[0])
    assert "[magenta]● 50 nodes[/magenta]" in header_str
    assert "[bold blue]" in header_str
    assert "[bold cyan]" not in header_str






















