import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web
from click.testing import CliRunner
import pytest

from spritzle.daemon.main import (
    APP_KEY_CONFIG,
    APP_KEY_CORE,
    APP_KEY_IDENTITY,
    APP_KEY_KEY_MANAGER,
    APP_KEY_LOG,
    check_libtorrent,
    create_app,
    debug_middleware,
    error_middleware,
    main as spritzled_cli,
    run_daemon,
)


def test_check_libtorrent():
    # Success case (libtorrent is installed in the test environment)
    check_libtorrent()

    # Failure case
    with patch.dict(sys.modules, {"libtorrent": None}):
        with pytest.raises(SystemExit) as exc_info:
            check_libtorrent()
        assert exc_info.value.code == 1


def test_spritzled_version_and_help():
    runner = CliRunner()
    res_help = runner.invoke(spritzled_cli, ["--help"])
    assert res_help.exit_code == 0
    assert "Manage API keys" in res_help.output


def test_key_management_cli(tmp_path):
    runner = CliRunner()
    cfg_dir = tmp_path / "config"
    st_dir = tmp_path / "state"
    cfg_dir.mkdir()
    st_dir.mkdir()

    # 1. List when empty
    res_list_empty = runner.invoke(
        spritzled_cli,
        ["key", "list", "-c", str(cfg_dir), "-s", str(st_dir)],
    )
    assert res_list_empty.exit_code == 0
    assert "No API keys found." in res_list_empty.output

    # 2. Create key
    res_create = runner.invoke(
        spritzled_cli,
        ["key", "create", "-n", "agent_key", "-c", str(cfg_dir), "-s", str(st_dir)],
    )
    assert res_create.exit_code == 0
    assert "Created API key for 'agent_key'" in res_create.output

    # 3. List with created key
    res_list = runner.invoke(
        spritzled_cli,
        ["key", "list", "-c", str(cfg_dir), "-s", str(st_dir)],
    )
    assert res_list.exit_code == 0
    assert "agent_key" in res_list.output
    assert "active" in res_list.output

    # 4. Revoke key
    res_revoke = runner.invoke(
        spritzled_cli,
        ["key", "revoke", "agent_key", "-c", str(cfg_dir), "-s", str(st_dir)],
    )
    assert res_revoke.exit_code == 0
    assert "Revoked API key: agent_key" in res_revoke.output

    # 5. Revoke nonexistent key
    res_revoke_fail = runner.invoke(
        spritzled_cli,
        ["key", "revoke", "nonexistent_key", "-c", str(cfg_dir), "-s", str(st_dir)],
    )
    assert res_revoke_fail.exit_code == 1
    assert "API key not found" in res_revoke_fail.output


async def test_debug_middleware():
    log_mock = MagicMock()
    app = {APP_KEY_LOG: log_mock}

    # 1. Form urlencoded request
    req1 = MagicMock()
    req1.app = app
    req1.content_type = "application/x-www-form-urlencoded"
    req1.post = AsyncMock(return_value={"field": "val"})
    rel1 = MagicMock()
    rel1.path = "/test"
    req1.rel_url = rel1
    req1.method = "POST"
    req1.headers = {"Authorization": "secret", "Content-Type": "application/x-www-form-urlencoded"}

    handler1 = AsyncMock(return_value=web.Response(text="ok"))
    res1 = await debug_middleware(req1, handler1)
    assert res1.text == "ok"
    assert log_mock.debug.called

    # 2. Non-utf8 binary data on /auth
    req2 = MagicMock()
    req2.app = app
    req2.content_type = "application/octet-stream"
    req2.text = AsyncMock(side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"))
    rel2 = MagicMock()
    rel2.path = "/auth"
    req2.rel_url = rel2
    req2.method = "POST"
    req2.headers = {"X-Api-Key": "secret"}

    handler2 = AsyncMock(return_value=web.Response(text="ok"))
    res2 = await debug_middleware(req2, handler2)
    assert res2.text == "ok"


async def test_error_middleware():
    import json
    log_mock = MagicMock()
    app = {APP_KEY_LOG: log_mock}

    # 1. Successful response (< 400) passes through
    req = MagicMock()
    req.app = app
    handler_ok = AsyncMock(return_value=web.Response(status=200, text="success"))
    res_ok = await error_middleware(req, handler_ok)
    assert res_ok.status == 200

    # 2. HTTPException (e.g. 404)
    handler_404 = AsyncMock(side_effect=web.HTTPNotFound(reason="Torrent Not Found", text="Custom 404"))
    res_404 = await error_middleware(req, handler_404)
    assert res_404.status == 404
    data_404 = json.loads(res_404.text)
    assert data_404["status"] == 404
    assert data_404["message"] == "Custom 404"

    # 3. Unhandled Exception (500)
    handler_500 = AsyncMock(side_effect=RuntimeError("database exploded"))
    res_500 = await error_middleware(req, handler_500)
    assert res_500.status == 500
    data_500 = json.loads(res_500.text)
    assert data_500["status"] == 500
    assert data_500["reason"] == "Internal Server Error"
    assert data_500["message"] == "An internal error occurred in Spritzle."


def test_create_app(core):
    log = MagicMock()
    app = create_app(core, log)
    assert app[APP_KEY_LOG] is log
    assert app[APP_KEY_CORE] is core
    assert app[APP_KEY_CONFIG] is core.config
    assert app[APP_KEY_IDENTITY] is core.identity
    assert app[APP_KEY_KEY_MANAGER] is core.key_manager


def test_run_daemon_lock_conflict(tmp_path):
    cfg_dir = tmp_path / "cfg"
    st_dir = tmp_path / "st"
    cfg_dir.mkdir()
    st_dir.mkdir()

    with patch("fcntl.lockf", side_effect=IOError("locked")):
        with pytest.raises(SystemExit) as exc_info:
            run_daemon(config_dir=str(cfg_dir), state_dir=str(st_dir))
        assert exc_info.value.code == 1


def test_run_daemon_bind_error(tmp_path):
    cfg_dir = tmp_path / "cfg"
    st_dir = tmp_path / "st"
    cfg_dir.mkdir()
    st_dir.mkdir()

    with patch("aiohttp.web.run_app", side_effect=OSError("Address already in use")):
        with pytest.raises(SystemExit) as exc_info:
            run_daemon(config_dir=str(cfg_dir), state_dir=str(st_dir))
        assert exc_info.value.code == 1


def test_setup_logger_with_logfile(tmp_path):
    from spritzle.daemon.logger import setup_logger
    log_file = tmp_path / "daemon.log"
    logger = setup_logger(name="test_logger_logfile", logfile=str(log_file), level="INFO")
    logger.info("testing logfile write")
    assert log_file.exists()
    assert "testing logfile write" in log_file.read_text()


def test_daemon_identity_oserror(tmp_path):
    from spritzle.daemon.identity import Identity
    st_dir = tmp_path / "identity_state"
    st_dir.mkdir()
    id_file = st_dir / "identity"
    id_file.write_text("old_id")

    with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
        identity = Identity(state_dir=st_dir)
        assert identity.daemon_id.startswith("spz_d_")
