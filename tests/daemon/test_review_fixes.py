#
# tests/daemon/test_review_fixes.py
#
import asyncio
from unittest.mock import MagicMock, patch

from aiohttp import test_utils, web
import libtorrent as lt
import pytest

from spritzle.daemon.core import Core
from spritzle.daemon.main import debug_middleware
from spritzle.daemon.resource.torrent import get_torrent_list_by_query, validate_torrent_url
from spritzle.daemon.torrent import Torrent


def test_validate_torrent_url_ssrf():
    # Magnet links bypass
    assert validate_torrent_url("magnet:?xt=urn:btih:0123456789012345678901234567890123456789")

    # Localhost and private IPs rejected by default
    with pytest.raises(web.HTTPBadRequest, match="not allowed"):
        validate_torrent_url("http://localhost:8080/test.torrent")

    with pytest.raises(web.HTTPBadRequest, match="not allowed"):
        validate_torrent_url("http://127.0.0.1:8080/test.torrent")

    with pytest.raises(web.HTTPBadRequest, match="not allowed"):
        validate_torrent_url("http://10.0.0.1/test.torrent")

    with pytest.raises(web.HTTPBadRequest, match="not allowed"):
        validate_torrent_url("http://192.168.1.1/test.torrent")

    with pytest.raises(web.HTTPBadRequest, match="not allowed"):
        validate_torrent_url("http://172.16.0.1/test.torrent")

    # Loopback allowed with explicit flag
    url = "http://127.0.0.1:8080/test.torrent"
    assert validate_torrent_url(url, allow_loopback=True) == url


async def test_torrent_remove_option_escalation():
    core = MagicMock()
    core.session = MagicMock()
    core.alert = MagicMock()
    torrent = Torrent(core)

    handle = MagicMock()
    handle.info_hash.return_value = "dummy_hash"

    loop = asyncio.get_running_loop()
    task1 = loop.create_task(torrent.remove(handle, 0, timeout=1.0))
    await asyncio.sleep(0.01)

    # Second removal concurrently requests delete_files
    task2 = loop.create_task(
        torrent.remove(handle, int(lt.options_t.delete_files), timeout=1.0)
    )
    await asyncio.sleep(0.01)

    # Verify options escalated to include delete_files
    assert torrent.in_flight_options["dummy_hash"] == int(lt.options_t.delete_files)
    core.session.remove_torrent.assert_called_with(
        handle, int(lt.options_t.delete_files)
    )

    # Fire alerts
    remove_alert = MagicMock()
    remove_alert.info_hash = "dummy_hash"
    delete_alert = MagicMock()
    delete_alert.info_hash = "dummy_hash"

    await torrent._on_torrent_removed_alert(remove_alert)
    await torrent._on_torrent_deleted_alert(delete_alert)

    await task1
    await task2
    assert "dummy_hash" not in torrent.in_flight_options


async def test_debug_middleware_redacts_api_key(caplog):
    import logging
    from spritzle.daemon.keys import APP_KEY_LOG

    app = web.Application(middlewares=[debug_middleware])
    app[APP_KEY_LOG] = logging.getLogger("spritzle.test")

    async def dummy_handler(request):
        return web.Response(text="ok")

    app.router.add_get("/test", dummy_handler)

    client = test_utils.TestClient(test_utils.TestServer(app))
    await client.start_server()
    try:
        with caplog.at_level("DEBUG"):
            resp = await client.get(
                "/test",
                headers={
                    "x-api-key": "spritzle_secret_key_12345",
                    "authorization": "Bearer token123",
                },
            )
            assert resp.status == 200

        logged_text = caplog.text
        assert "spritzle_secret_key_12345" not in logged_text
        assert "x-api-key" in logged_text.lower()
        assert "***REDACTED***" in logged_text
    finally:
        await client.close()


def test_query_list_op_ne_and_invalid_regex():
    statuses = [
        {"info_hash": "h1", "string": "archlinux", "spritzle.tags": ["linux", "iso"]},
        {"info_hash": "h2", "string": "debian", "spritzle.tags": ["linux", "deb"]},
        {"info_hash": "h3", "string": "freebsd", "spritzle.tags": ["bsd"]},
    ]

    # Test list op == ne
    # Exclude torrents with 'iso' tag
    res = get_torrent_list_by_query({"spritzle.tags.ne": "iso"}, statuses)
    assert res == ["h2", "h3"]

    # Exclude torrents with 'linux' tag
    res2 = get_torrent_list_by_query({"spritzle.tags.ne": "linux"}, statuses)
    assert res2 == ["h3"]

    # Test invalid regex handling
    with pytest.raises(web.HTTPBadRequest, match="Invalid regular expression"):
        get_torrent_list_by_query({"string": "[unclosed("}, statuses)


async def test_storage_moved_alerts(tmp_path):
    config = MagicMock()
    core = Core(config, state_dir=tmp_path)
    core.session = MagicMock()
    core.resume_data = MagicMock()
    core.resume_data.save_torrent = MagicMock()
    core.hooks = MagicMock()
    core.hooks.run_hooks = MagicMock()

    handle = MagicMock()
    handle.info_hash.return_value = "hash1234"
    handle.is_valid.return_value = True

    # storage_moved_alert
    alert = MagicMock()
    alert.handle = handle
    alert.storage_path.return_value = "/new/storage/path"

    await core.on_storage_moved_alert(alert)
    core.resume_data.save_torrent.assert_called_once_with(handle)

    # storage_moved_failed_alert
    fail_alert = MagicMock()
    fail_alert.handle = handle
    fail_alert.message.return_value = "Disk full"

    await core.on_storage_moved_failed_alert(fail_alert)
    assert core.torrent_data["hash1234"]["last_error"] == "Disk full"
    core.hooks.run_hooks.assert_called_with("storage_moved_failed_alert", "hash1234", "")


async def test_save_session_state_atomic(tmp_path):
    config = MagicMock()
    core = Core(config, state_dir=tmp_path)
    core.session = MagicMock()
    core.session.save_state.return_value = None

    state_file = tmp_path / "session.state"
    assert not state_file.exists()

    with patch("spritzle.daemon.core.lt.bencode", return_value=b"test_state_data"):
        await core.save_session_state()

    assert state_file.is_file()
    assert state_file.read_bytes() == b"test_state_data"
    assert not (tmp_path / ".session.state.tmp").exists()


async def test_post_torrent_method_invalid_utf8_payload(cli):
    torrent_address = str(cli.make_url("/test_torrents/random_one_file.torrent"))
    resp = await cli.post("/torrent", json={"url": torrent_address})
    assert resp.status == 201
    info_hash = (await resp.json())["info_hash"]

    # Send non-utf8 binary data to POST /torrent/{tid}/pause
    raw_bytes = b"\xff\xfe\xfd\x80"
    resp = await cli.post(
        f"/torrent/{info_hash}/pause",
        data=raw_bytes,
        headers={"Content-Type": "application/json"},
    )
    # Must return 400 Bad Request, NOT 500 Internal Server Error
    assert resp.status == 400
    data = await resp.json()
    assert "Invalid payload encoding" in data.get("message", "")


async def test_delete_torrent_bulk_with_keys_query(cli):
    torrent_address = str(cli.make_url("/test_torrents/random_one_file.torrent"))
    resp = await cli.post("/torrent", json={"url": torrent_address})
    assert resp.status == 201
    info_hash = (await resp.json())["info_hash"]

    # DELETE /torrent with keys=name should not fail with TypeError
    resp = await cli.delete("/torrent?keys=name")
    assert resp.status == 200

    # Verify torrent is deleted
    resp = await cli.get(f"/torrent/{info_hash}")
    assert resp.status == 404


async def test_put_session_settings_rejects_null_for_string(cli):
    resp = await cli.put("/session/settings", json={"user_agent": None})
    assert resp.status == 400
    data = await resp.json()
    assert "does not allow null values" in data.get("message", "")


def test_core_state_dir_from_environment(monkeypatch, tmp_path):
    env_dir = tmp_path / "custom_state"
    monkeypatch.setenv("SPRITZLE_STATE_DIR", str(env_dir))
    config = MagicMock()
    core = Core(config, state_dir=None)
    assert core.state_dir == env_dir


def test_corrupt_config_backup_created(tmp_path):
    from spritzle.daemon.config import Config
    cfg_file = tmp_path / "daemon.toml"
    cfg_file.write_text("invalid [ toml syntax {[[")
    config = Config(config_dir=tmp_path)
    assert config._unparseable is True
    config["save_resume_data_interval"] = 120
    bak_file = tmp_path / "daemon.toml.bak"
    assert bak_file.exists()
    assert bak_file.read_text() == "invalid [ toml syntax {[["
    assert config["save_resume_data_interval"] == 120


def test_ipv6_host_bracketed_in_url(tmp_path):
    from spritzle.daemon.api_keys import KeyManager
    km = KeyManager(tmp_path)
    host = "::1"
    port = 17382
    bracketed_host = f"[{host}]" if ":" in host and not (host.startswith("[") and host.endswith("]")) else host
    data = km.ensure_local_client_remote(f"http://{bracketed_host}:{port}", "test_daemon_id")
    assert data["url"] == "http://[::1]:17382"


def test_lookup_extract_hashes_handles_dicts():
    from spritzle.cli.lookup import _extract_hashes
    input_data = [
        {"info_hash": "44a040be6d74d8d290cd20128788864cbf770719", "name": "arch"},
        "d3b07384d113edec49eaa6238ad5ff00fc7b0553",
    ]
    extracted = _extract_hashes(input_data)
    assert extracted == [
        "44a040be6d74d8d290cd20128788864cbf770719",
        "d3b07384d113edec49eaa6238ad5ff00fc7b0553",
    ]


def test_to_bool_ssrf_normalization():
    from spritzle.daemon.resource.torrent import _to_bool
    assert _to_bool("false") is False
    assert _to_bool("False") is False
    assert _to_bool("0") is False
    assert _to_bool("no") is False
    assert _to_bool("off") is False
    assert _to_bool(False) is False
    assert _to_bool("true") is True
    assert _to_bool("True") is True
    assert _to_bool("1") is True
    assert _to_bool("yes") is True
    assert _to_bool("on") is True
    assert _to_bool(True) is True


async def test_session_reset_all_string_boolean(cli):
    # Passing "all": "false" without keys should fail with HTTP 400
    resp = await cli.post("/session/settings/reset", json={"all": "false"})
    assert resp.status == 400
    data = await resp.json()
    assert "Must specify 'keys' list or 'all: true'" in data.get("message", "")


async def test_clear_error_clears_torrent_data(cli, core):
    torrent_address = str(cli.make_url("/test_torrents/random_one_file.torrent"))
    resp = await cli.post("/torrent", json={"url": torrent_address})
    assert resp.status == 201
    info_hash = (await resp.json())["info_hash"]

    # Artificially simulate an error recorded in core.torrent_data
    core.torrent_data[info_hash]["last_error"] = "Fatal error writing piece"

    # Verify GET /torrent/{tid} reports last_error
    resp = await cli.get(f"/torrent/{info_hash}")
    assert resp.status == 200
    assert (await resp.json()).get("last_error") == "Fatal error writing piece"

    # Call POST /torrent/{tid}/clear_error
    resp = await cli.post(f"/torrent/{info_hash}/clear_error")
    assert resp.status == 200

    # Verify last_error is cleared from core.torrent_data and GET response
    assert "last_error" not in core.torrent_data.get(info_hash, {})
    resp = await cli.get(f"/torrent/{info_hash}")
    assert resp.status == 200
    assert "last_error" not in await resp.json()


async def test_query_and_projection_supports_last_error(cli, core):
    torrent_address = str(cli.make_url("/test_torrents/random_one_file.torrent"))
    resp = await cli.post("/torrent", json={"url": torrent_address})
    assert resp.status == 201
    info_hash = (await resp.json())["info_hash"]

    core.torrent_data[info_hash]["last_error"] = "Network timeout"

    # Requesting last_error in keys should succeed without HTTP 400
    resp = await cli.get("/torrent?keys=name,last_error")
    assert resp.status == 200
    items = await resp.json()
    assert len(items) >= 1
    matched = next((item for item in items if item.get("info_hash") == info_hash), None)
    assert matched is not None
    assert matched.get("last_error") == "Network timeout"

    # Filtering by last_error should succeed without 400
    resp = await cli.get("/torrent?last_error=Network timeout")
    assert resp.status == 200
    assert info_hash in await resp.json()


async def test_on_state_changed_alert_invalid_handle(core):
    alert = MagicMock()
    handle = MagicMock()
    handle.is_valid.return_value = False
    handle.need_save_resume_data.side_effect = RuntimeError("torrent_handle is invalid")
    alert.handle = handle

    # Must not raise RuntimeError when handle is invalid
    await core.on_state_changed_alert(alert)
    handle.need_save_resume_data.assert_not_called()


async def test_resume_data_write_failure_resolves_false(core, tmp_path):
    info_hash = "44a040be6d74d8d290cd20128788864cbf770719"
    fut = asyncio.get_running_loop().create_future()

    # Pass an invalid/unwritable path to simulate disk write failure
    bad_path = tmp_path / "nonexistent_subfolder" / "unwritable" / "file.resume"
    await core.resume_data._write_data(bad_path, b"dummy data", info_hash, {fut})
    assert fut.done()
    assert fut.result() is False

    # Also test on_save_resume_data_failed_alert resolves future to False
    fut2 = asyncio.get_running_loop().create_future()
    core.resume_data.resume_data_futures[info_hash] = {fut2}

    alert = MagicMock()
    alert.torrent_name = "test_torrent"
    alert.error.message.return_value = "disk error"
    alert.handle.info_hash.return_value = info_hash
    await core.resume_data.on_save_resume_data_failed_alert(alert)
    assert fut2.done()
    assert fut2.result() is False


def test_config_snapshot_and_restore_no_default_pollution(tmp_path):
    from spritzle.daemon.config import Config
    cfg_file = tmp_path / "daemon.toml"
    cfg_file.write_text('my_custom_option = "abc"\n')
    config = Config(config_dir=tmp_path)

    # Verify initial state: default key not in doc
    assert "save_resume_data_interval" not in config._doc
    snapshot = config.snapshot()

    # Apply changes
    config["save_resume_data_interval"] = 120
    config["my_custom_option"] = "xyz"
    assert "save_resume_data_interval" in config._doc

    # Restore snapshot on simulated rollback
    config.restore(snapshot)
    assert config["my_custom_option"] == "abc"
    # The default key must NOT be serialized to the document or disk file
    assert "save_resume_data_interval" not in config._doc
    saved_text = cfg_file.read_text()
    assert "save_resume_data_interval" not in saved_text
    assert 'my_custom_option = "abc"' in saved_text


async def test_delete_torrent_timeout_cleans_state(cli, core):
    torrent_address = str(cli.make_url("/test_torrents/random_one_file.torrent"))
    resp = await cli.post("/torrent", json={"url": torrent_address})
    assert resp.status == 201
    info_hash = (await resp.json())["info_hash"]

    core.resume_data.delete = MagicMock()
    with patch.object(core.torrent, "remove", side_effect=asyncio.TimeoutError()):
        resp = await cli.delete(f"/torrent/{info_hash}")
        assert resp.status == 504
        core.resume_data.delete.assert_called_once_with(info_hash)
        assert info_hash not in core.torrent_data


def test_core_state_dir_precedence(tmp_path, monkeypatch):
    from pathlib import Path
    from spritzle.daemon.config import Config
    from spritzle.daemon.core import Core

    cfg = Config(in_memory=True)

    # 1. Hardcoded default when nothing is set
    monkeypatch.delenv("SPRITZLE_STATE_DIR", raising=False)
    core_default = Core(cfg)
    assert core_default.state_dir == Path.home() / ".local" / "share" / "spritzle" / "state"

    # 2. Config file setting overrides default
    cfg["state_dir"] = str(tmp_path / "from_config")
    core_config = Core(cfg)
    assert core_config.state_dir == tmp_path / "from_config"

    # 3. Environment variable overrides config file
    monkeypatch.setenv("SPRITZLE_STATE_DIR", str(tmp_path / "from_env"))
    core_env = Core(cfg)
    assert core_env.state_dir == tmp_path / "from_env"

    # 4. Explicit parameter overrides environment variable
    core_explicit = Core(cfg, state_dir=tmp_path / "from_explicit")
    assert core_explicit.state_dir == tmp_path / "from_explicit"


def test_spritzled_key_custom_state_dir(tmp_path):
    from click.testing import CliRunner
    from spritzle.daemon.main import main as spritzled_cli

    runner = CliRunner()
    state_dir = tmp_path / "custom_state"
    config_dir = tmp_path / "custom_config"

    # 1. Create key with -s / --state-dir
    res = runner.invoke(
        spritzled_cli,
        ["key", "create", "-n", "testkey", "-c", str(config_dir), "-s", str(state_dir)],
    )
    assert res.exit_code == 0
    assert "Created API key for 'testkey'" in res.output

    # Verify keys.json was written inside custom state_dir
    assert (state_dir / "keys.json").exists()

    # 2. List keys using -s
    res_list = runner.invoke(
        spritzled_cli,
        ["key", "list", "-c", str(config_dir), "-s", str(state_dir)],
    )
    assert res_list.exit_code == 0
    assert "testkey" in res_list.output

    # 3. Test parent option inheritance: spritzled -s ... key list
    res_parent = runner.invoke(
        spritzled_cli,
        ["-c", str(config_dir), "-s", str(state_dir), "key", "list"],
    )
    assert res_parent.exit_code == 0
    assert "testkey" in res_parent.output

    # 4. Revoke key
    key_id = res.output.split("(")[1].split(")")[0]
    res_revoke = runner.invoke(
        spritzled_cli,
        ["key", "revoke", key_id, "-c", str(config_dir), "-s", str(state_dir)],
    )
    assert res_revoke.exit_code == 0
    assert f"Revoked API key: {key_id}" in res_revoke.output


