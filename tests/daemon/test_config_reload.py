import asyncio
from pathlib import Path
import tempfile
import time

from click.testing import CliRunner

from spritzle.daemon.config import Config
from spritzle.daemon.core import Core
from spritzle.daemon.main import create_app
from spritzle.cli.main import cli as spritzle_cli


def test_config_reload_basic():
    with tempfile.TemporaryDirectory() as tempdir:
        config_path = Path(tempdir, "daemon.toml")
        config_path.write_text("default_save_path = '/tmp/path1'\nsave_resume_data_interval = 60\n")

        config = Config(config_dir=tempdir)
        assert config["default_save_path"] == "/tmp/path1"
        assert config["save_resume_data_interval"] == 60

        # Without modifying the file, reload returns False
        assert config.reload() is False

        # Modify file on disk (ensure mtime changes)
        time.sleep(0.05)
        config_path.write_text("default_save_path = '/tmp/path2'\nsave_resume_data_interval = 30\n")

        assert config.reload() is True
        assert config["default_save_path"] == "/tmp/path2"
        assert config["save_resume_data_interval"] == 30

        # Subsequent reload with no disk change returns False
        assert config.reload() is False

        # Forced reload returns True
        assert config.reload(force=True) is True


def test_config_reload_syntax_error_preserves_state():
    with tempfile.TemporaryDirectory() as tempdir:
        config_path = Path(tempdir, "daemon.toml")
        config_path.write_text("default_save_path = '/tmp/valid'\nsave_resume_data_interval = 60\n")

        config = Config(config_dir=tempdir)
        assert config["default_save_path"] == "/tmp/valid"

        # Write invalid TOML syntax to disk
        time.sleep(0.05)
        config_path.write_text("default_save_path = [unclosed syntax error\n")

        # Reload should fail gracefully without wiping config
        assert config.reload() is False
        assert config["default_save_path"] == "/tmp/valid"
        assert config.get("default_save_path") == "/tmp/valid"


def test_config_self_save_deduplication():
    with tempfile.TemporaryDirectory() as tempdir:
        config = Config(config_dir=tempdir)
        config["custom_key"] = "original_value"

        # config.save() was called by __setitem__, so reload should see no new changes
        assert config.reload() is False
        assert config["custom_key"] == "original_value"


def test_config_change_callbacks():
    with tempfile.TemporaryDirectory() as tempdir:
        config_path = Path(tempdir, "daemon.toml")
        config_path.write_text("default_save_path = '/tmp/one'\n")

        config = Config(config_dir=tempdir)
        called = []

        def callback(cfg):
            called.append(cfg["default_save_path"])

        config.add_change_callback(callback)

        time.sleep(0.05)
        config_path.write_text("default_save_path = '/tmp/two'\n")
        assert config.reload() is True
        assert called == ["/tmp/two"]

        # Remove callback
        config.remove_change_callback(callback)
        time.sleep(0.05)
        config_path.write_text("default_save_path = '/tmp/three'\n")
        assert config.reload() is True
        assert called == ["/tmp/two"]


async def test_config_file_watcher_detects_change():
    with tempfile.TemporaryDirectory() as tempdir:
        config_path = Path(tempdir, "daemon.toml")
        config_path.write_text("default_save_path = '/tmp/watcher1'\nconfig_watch_interval = 0.05\n")

        config = Config(config_dir=tempdir)
        state_dir = Path(tempdir, "state")
        core = Core(config, state_dir=state_dir)
        await core.start(settings={"alert_mask": 0})

        try:
            assert core.config["default_save_path"] == "/tmp/watcher1"

            # Modify file on disk
            await asyncio.sleep(0.06)
            config_path.write_text("default_save_path = '/tmp/watcher2'\nconfig_watch_interval = 0.05\n")

            # Wait for watcher to trigger
            for _ in range(20):
                await asyncio.sleep(0.05)
                if core.config.get("default_save_path") == "/tmp/watcher2":
                    break

            assert core.config["default_save_path"] == "/tmp/watcher2"
        finally:
            await core.stop()


async def test_sighup_handling():
    with tempfile.TemporaryDirectory() as tempdir:
        config_path = Path(tempdir, "daemon.toml")
        config_path.write_text("default_save_path = '/tmp/hup1'\n")

        config = Config(config_dir=tempdir)
        state_dir = Path(tempdir, "state")
        core = Core(config, state_dir=state_dir)
        await core.start(settings={"alert_mask": 0})

        try:
            assert core.config["default_save_path"] == "/tmp/hup1"

            # Update file on disk
            await asyncio.sleep(0.05)
            config_path.write_text("default_save_path = '/tmp/hup2'\n")

            # Simulate SIGHUP trigger
            core._on_sighup()

            # Await background tasks in core._tasks
            for _ in range(10):
                await asyncio.sleep(0.05)
                if core.config.get("default_save_path") == "/tmp/hup2":
                    break

            assert core.config["default_save_path"] == "/tmp/hup2"
        finally:
            await core.stop()


async def test_api_config_reload(aiohttp_client):
    with tempfile.TemporaryDirectory() as tempdir:
        config_path = Path(tempdir, "daemon.toml")
        config_path.write_text("default_save_path = '/tmp/api1'\n")

        config = Config(config_dir=tempdir)
        state_dir = Path(tempdir, "state")
        core = Core(config, state_dir=state_dir)

        import logging
        log = logging.getLogger("spritzle")
        app = create_app(core, log)
        client = await aiohttp_client(app)

        try:
            # First reload with no changes
            resp = await client.post("/config/reload")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"

            # Now modify on disk
            await asyncio.sleep(0.05)
            config_path.write_text("default_save_path = '/tmp/api2'\n")

            resp = await client.post("/config/reload")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
            assert data["reloaded"] is True
            assert core.config["default_save_path"] == "/tmp/api2"
        finally:
            await client.close()
            await core.stop()


def test_cli_daemon_config_reload(cli):
    runner = CliRunner()
    import json

    result = runner.invoke(spritzle_cli, ["daemon-config", "--reload"])
    assert result.exit_code == 0
    assert "Daemon configuration" in result.output

    result_json = runner.invoke(spritzle_cli, ["daemon-config", "--reload", "--json"])
    assert result_json.exit_code == 0
    data = json.loads(result_json.output)
    assert data.get("status") == "ok"


async def test_resume_data_interval_reload(monkeypatch):
    with tempfile.TemporaryDirectory() as tempdir:
        config_path = Path(tempdir, "daemon.toml")
        config_path.write_text("save_resume_data_interval = 3600\n")

        config = Config(config_dir=tempdir)
        state_dir = Path(tempdir, "state")
        core = Core(config, state_dir=state_dir)
        await core.start(settings={"alert_mask": 0})

        try:
            assert core.config["save_resume_data_interval"] == 3600
            saved_count = 0
            original_save_all = core.resume_data.save_all

            async def mock_save_all():
                nonlocal saved_count
                saved_count += 1
                return await original_save_all()

            monkeypatch.setattr(core.resume_data, "save_all", mock_save_all)

            # Update config file with short interval and reload
            await asyncio.sleep(0.05)
            config_path.write_text("save_resume_data_interval = 0.05\n")
            await core.reload_config()

            # Verify save_all triggers under the new short interval
            for _ in range(10):
                await asyncio.sleep(0.03)
                if saved_count > 0:
                    break

            assert saved_count > 0
        finally:
            await core.stop()
