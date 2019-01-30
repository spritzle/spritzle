import asyncio
from unittest.mock import Mock

import libtorrent as lt
import pytest

from spritzle.alert import Alert
from spritzle.torrent import Torrent


class MockAlert(Alert):
    def __init__(self):
        super().__init__()
        self._alerts = []

    def _pop_alerts(self):
        result = self._alerts
        self._alerts = []
        self.event.clear()
        return result

    async def push_alert(self, alert_type, **kwargs):
        alert = Mock(**{
            'what.return_value': alert_type,
            'category.return_value': 0
        })
        alert.configure_mock(**kwargs)
        self._alerts.append(alert)
        self.event.set()

    async def start(self, session):
        self.session = Mock(
            pop_alerts=self._pop_alerts
        )
        self.run = True
        self.pop_alerts_task = asyncio.ensure_future(self.pop_alerts())


@pytest.fixture
async def mock_alert():
    mock_alert = MockAlert()
    await mock_alert.start(None)
    yield mock_alert
    await mock_alert.stop()


async def test_torrent_remove(loop, mock_alert):
    core = Mock(alert=mock_alert)
    torrent = Torrent(core)

    info_hash = '1234567890'
    torrent_handle = Mock(**{
        'info_hash.return_value': info_hash
    })

    remove_task = loop.create_task(torrent.remove(torrent_handle))
    # Make sure we allow a context switch to let remove_task run
    await asyncio.sleep(0)
    core.session.remove_torrent.assert_called_once_with(torrent_handle, 0)
    assert not remove_task.done()
    await core.alert.push_alert('torrent_removed_alert', info_hash=info_hash)
    await asyncio.wait_for(remove_task, 1)
    core.reset_mock()

    remove_task = loop.create_task(torrent.remove(torrent_handle, lt.options_t.delete_files))
    await asyncio.sleep(0)
    core.session.remove_torrent.assert_called_once_with(torrent_handle, lt.options_t.delete_files)
    assert not remove_task.done()
    await core.alert.push_alert('torrent_removed_alert', info_hash=info_hash)
    assert not remove_task.done()
    await core.alert.push_alert('torrent_deleted_alert', info_hash=info_hash)
    await asyncio.wait_for(remove_task, 1)
