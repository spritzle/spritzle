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
import inspect
from aiohttp.test_utils import TestClient, TestServer, setup_test_loop, teardown_test_loop


@pytest.fixture
def loop():
    loop = setup_test_loop()
    yield loop
    teardown_test_loop(loop, fast=True)



@pytest.fixture
def aiohttp_client(loop):
    clients = []

    async def go(app_or_server, *, server_kwargs=None, **kwargs):
        if not isinstance(app_or_server, TestServer):
            skw = dict(server_kwargs) if server_kwargs else {}
            server = TestServer(app_or_server, **skw)
        else:
            server = app_or_server
        client = TestClient(server, **kwargs)
        await client.start_server()
        clients.append(client)
        return client

    yield go

    async def finalize():
        while clients:
            await clients.pop().close()

    loop.run_until_complete(finalize())


def pytest_pyfunc_call(pyfuncitem):
    if inspect.iscoroutinefunction(pyfuncitem.function):
        loop = pyfuncitem.funcargs.get("loop")
        needs_teardown = False
        if loop is None:
            loop = setup_test_loop()
            needs_teardown = True
        try:
            testargs = {
                arg: pyfuncitem.funcargs[arg]
                for arg in pyfuncitem._fixtureinfo.argnames
            }
            loop.run_until_complete(pyfuncitem.obj(**testargs))
        finally:
            if needs_teardown:
                teardown_test_loop(loop, fast=True)
        return True



@pytest.fixture(scope="function")
def core(loop, monkeypatch):
    downloads_dir = Path(tempfile.mkdtemp(prefix="spritzle-test-downloads"))
    config = Config(in_memory=True, config_dir="/tmp")
    config["default_save_path"] = str(downloads_dir)
    state_dir = Path(tempfile.mkdtemp(prefix="spritzle-test-state"))
    config_dir = Path(tempfile.mkdtemp(prefix="spritzle-test-config"))
    monkeypatch.setenv("SPRITZLE_STATE_DIR", str(state_dir))
    monkeypatch.setenv("SPRITZLE_CONFIG", str(config_dir))
    monkeypatch.setenv("SPRITZLE_SAVE_PATH", str(downloads_dir))
    monkeypatch.setenv("SPRITZLE_ALLOW_LOOPBACK_URL", "1")
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
    try:
        loop.run_until_complete(core.stop())
    except Exception:
        pass
    shutil.rmtree(str(state_dir), ignore_errors=True)
    shutil.rmtree(str(config_dir), ignore_errors=True)
    shutil.rmtree(str(downloads_dir), ignore_errors=True)


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
