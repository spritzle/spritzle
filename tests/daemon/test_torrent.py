import asyncio
from unittest.mock import Mock

import libtorrent as lt
import pytest

from spritzle.daemon.alert import Alert
from spritzle.daemon.torrent import Torrent


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
        alert = Mock(**{"__class__.__name__": alert_type, "category.return_value": 0})
        alert.configure_mock(**kwargs)
        self._alerts.append(alert)
        self.event.set()

    async def start(self, session):
        self.loop = asyncio.get_event_loop()
        self.session = Mock(pop_alerts=self._pop_alerts)
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

    info_hash = "1234567890"
    torrent_handle = Mock(**{"info_hash.return_value": info_hash})

    remove_task = loop.create_task(torrent.remove(torrent_handle))
    # Make sure we allow a context switch to let remove_task run
    await asyncio.sleep(0)
    core.session.remove_torrent.assert_called_once_with(torrent_handle, 0)
    assert not remove_task.done()
    await core.alert.push_alert("torrent_removed_alert", info_hash=info_hash)
    await asyncio.wait_for(remove_task, 1)
    core.reset_mock()

    remove_task = loop.create_task(
        torrent.remove(torrent_handle, lt.options_t.delete_files)
    )
    await asyncio.sleep(0)
    core.session.remove_torrent.assert_called_once_with(
        torrent_handle, lt.options_t.delete_files
    )
    assert not remove_task.done()
    await core.alert.push_alert("torrent_removed_alert", info_hash=info_hash)
    assert not remove_task.done()
    await core.alert.push_alert("torrent_deleted_alert", info_hash=info_hash)
    await asyncio.wait_for(remove_task, 1)


async def test_untracked_torrent_alerts(loop, mock_alert):
    core = Mock(alert=mock_alert)
    torrent = Torrent(core)
    alert = Mock(info_hash="untracked_hash_123")
    # These should handle untracked alerts gracefully without raising KeyError
    await torrent._on_torrent_removed_alert(alert)
    await torrent._on_torrent_deleted_alert(alert)
    await torrent._on_torrent_delete_failed_alert(alert)


async def test_torrent_remove_timeout(loop, mock_alert):
    """
    Verifies that Torrent.remove() raises asyncio.TimeoutError when alerts are not received
    within the specified timeout, instead of hanging indefinitely.
    """
    core = Mock(alert=mock_alert)
    torrent = Torrent(core)
    info_hash = "1234567890"
    torrent_handle = Mock(**{"info_hash.return_value": info_hash})

    # When timeout occurs, it must raise TimeoutError
    with pytest.raises(asyncio.TimeoutError):
        await torrent.remove(torrent_handle, timeout=0.05)

    # And futures must be cleaned up from remove_torrent_futures and delete_torrent_futures
    assert info_hash not in torrent.remove_torrent_futures
    assert info_hash not in torrent.delete_torrent_futures


async def test_concurrent_remove_timeout_does_not_break_other_callers(loop, mock_alert):
    core = Mock(alert=mock_alert)
    torrent = Torrent(core)
    info_hash = "1234567890"
    torrent_handle = Mock(**{"info_hash.return_value": info_hash})

    # Caller 1 has a long timeout
    task1 = loop.create_task(torrent.remove(torrent_handle, timeout=1.0))
    # Caller 2 has a short timeout
    task2 = loop.create_task(torrent.remove(torrent_handle, timeout=0.02))

    await asyncio.sleep(0.05)
    # Caller 2 should have timed out
    assert task2.done()
    with pytest.raises(asyncio.TimeoutError):
        await task2

    # Now the alert arrives
    await core.alert.push_alert("torrent_removed_alert", info_hash=info_hash)

    # Caller 1 must finish successfully and NOT hang or time out
    await asyncio.wait_for(task1, timeout=0.5)
    assert task1.done()


async def test_torrent_remove_no_timeout_and_delete_failed(loop, mock_alert):
    from spritzle.daemon.torrent import AlertException
    core = Mock(alert=mock_alert)
    torrent = Torrent(core)
    info_hash = "1234567890"
    torrent_handle = Mock(**{"info_hash.return_value": info_hash})

    # Call with timeout=None and delete_files
    task = loop.create_task(torrent.remove(torrent_handle, options=lt.options_t.delete_files, timeout=None))
    await asyncio.sleep(0)
    # Push removed alert
    await core.alert.push_alert("torrent_removed_alert", info_hash=info_hash)
    # Push delete failed alert
    fail_alert = Mock(info_hash=info_hash)
    await torrent._on_torrent_delete_failed_alert(fail_alert)
    with pytest.raises(AlertException):
        await task



