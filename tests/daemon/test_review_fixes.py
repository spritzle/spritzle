#
# tests/daemon/test_review_fixes.py
#
import asyncio
from unittest.mock import MagicMock, patch

import aiohttp
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
