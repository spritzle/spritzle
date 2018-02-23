import tempfile
from pathlib import Path
import shutil

import pytest

from spritzle.core import Core
from spritzle.config import Config
from spritzle.tests.common import run_until_complete


@pytest.fixture(scope='function')
def core():
    config = Config(in_memory=True, config_dir='/tmp')
    state_dir = Path(tempfile.mkdtemp(prefix='spritzle-test'))
    core = Core(config, state_dir)

    @run_until_complete
    async def core_start():
        await core.start(
            settings={
                'enable_upnp': False,
                'enable_natpmp': False,
                'enable_lsd': False,
                'enable_dht': False,
                'anonymous_mode': True,
                'alert_mask': 0,
                'stop_tracker_timeout': 0,
            }
        )
    core_start()
    yield core

    @run_until_complete
    async def core_stop():
        await core.stop()
    core_stop()

    shutil.rmtree(str(state_dir))
