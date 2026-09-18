from functools import partial
import tempfile
import logging
from pathlib import Path
import shutil
from unittest.mock import patch

import aiohttp.web
import pytest

from spritzle.daemon.core import Core
from spritzle.daemon.config import Config
from spritzle.daemon.main import setup_app
from daemon.common import torrent_dir

pytest_plugins = "aiohttp.pytest_plugin"


@pytest.fixture(scope="function")
def core(loop, monkeypatch):
    config = Config(in_memory=True, config_dir="/tmp")
    state_dir = Path(tempfile.mkdtemp(prefix="spritzle-test-state"))
    config_dir = Path(tempfile.mkdtemp(prefix="spritzle-test-config"))
    monkeypatch.setenv("SPRITZLE_STATE_DIR", str(state_dir))
    monkeypatch.setenv("SPRITZLE_CONFIG", str(config_dir))
    core = Core(config, state_dir)
    settings = {
        "enable_upnp": False,
        "enable_natpmp": False,
        "enable_lsd": False,
        "enable_dht": False,
        "anonymous_mode": True,
        "alert_mask": 0,
        "stop_tracker_timeout": 0,
    }
    with patch.object(core, "start", partial(core.start, settings=settings)):
        yield core
    if core.session is not None:
        loop.run_until_complete(core.stop())
    shutil.rmtree(str(state_dir), ignore_errors=True)
    shutil.rmtree(str(config_dir), ignore_errors=True)


@pytest.fixture
def app(core):
    app = aiohttp.web.Application()
    log = logging.getLogger("spritzle")
    logging.basicConfig(level=logging.DEBUG)
    setup_app(app, core, log)
    app.router.add_static("/test_torrents", torrent_dir)
    return app


@pytest.fixture
def cli(loop, app, core, aiohttp_client):
    client = loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"host": "127.0.0.1", "port": 0})
    )
    core.key_manager.ensure_local_client_remote(
        f"http://127.0.0.1:{client.server.port}", core.identity.daemon_id
    )
    return client
