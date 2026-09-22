#
# test_alert.py
#
# Copyright (C) 2016 Andrew Resch <andrewresch@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.    If not, write to:
#   The Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor
#   Boston, MA    02110-1301, USA.
#

import asyncio
from typing import Any, cast
from unittest.mock import MagicMock, AsyncMock

import pytest

import spritzle.daemon.alert


class CategoryT:
    test_category1 = 1
    test_category2 = 2
    all_categories = 268435455


class AlertTest:
    def what(self):
        return self.__class__.__name__

    def category(self):
        return 1


class AlertTestOne(AlertTest):
    pass


class AlertTestTwo(AlertTest):
    def category(self):
        return 2


async def test_alert_stop():
    a = spritzle.daemon.alert.Alert()
    assert not a.run
    await a.start(MagicMock())
    await asyncio.sleep(0)
    assert a.run
    await a.stop()
    assert not a.run


async def test_pop_alerts(monkeypatch):
    session = MagicMock()

    alert_test_one = AlertTestOne()
    alert_test_two = AlertTestTwo()

    session.configure_mock(
        **{"pop_alerts.return_value": [alert_test_one, alert_test_two]}
    )

    monkeypatch.setattr("libtorrent.alert.category_t", CategoryT)
    a = spritzle.daemon.alert.Alert()
    a.alert_types = ["AlertTestOne", "AlertTestTwo", "AlertTestThree"]

    handler_one = AsyncMock()
    a.register_handler("AlertTestOne", handler_one)
    assert "AlertTestOne" in a.handlers

    handler_two = AsyncMock()
    a.register_handler("AlertTestTwo", handler_two)
    assert "AlertTestTwo" in a.handlers

    handler_three = AsyncMock()
    a.register_handler("test_category1", handler_three)
    assert "test_category1" in a.handlers

    await a.start(session)
    a.event.set()
    # Make sure the event.set() has woken up pop_alerts() before stopping.
    await asyncio.sleep(0)
    await a.stop()

    handler_one.assert_called_with(alert_test_one)
    handler_two.assert_called_with(alert_test_two)
    handler_three.assert_called_with(alert_test_one)


async def test_handler_validation():
    async def valid_handler(alert):
        pass

    def invalid_handler(alert):
        pass

    a = spritzle.daemon.alert.Alert()
    valid_alert_type = "torrent_paused_alert"
    valid_category = "storage_notification"
    invalid_alert_type = "invalid_alert_type"

    # Verify a valid handler doesn't raise anything
    a.register_handler(valid_alert_type, valid_handler)
    a.register_handler(valid_category, valid_handler)

    with pytest.raises(ValueError):
        a.register_handler(valid_alert_type, invalid_handler)

    with pytest.raises(ValueError):
        a.register_handler(invalid_alert_type, valid_handler)


async def test_alert_with_real_session_and_alert_fd():
    import libtorrent as lt

    ses = lt.session({
        "enable_dht": False,
        "enable_lsd": False,
        "enable_upnp": False,
        "enable_natpmp": False,
        "alert_mask": int(lt.alert.category_t.all_categories),
    })
    a = spritzle.daemon.alert.Alert()

    called = asyncio.Event()

    async def on_stats(alert):
        called.set()

    a.register_handler("session_stats_alert", on_stats)
    await a.start(ses)

    assert a._notify_r is not None
    assert a._notify_w is not None

    ses.post_session_stats()

    try:
        await asyncio.wait_for(called.wait(), timeout=2.0)
    finally:
        await a.stop()

    assert a._notify_r is None
    assert a._notify_w is None


async def test_alert_no_deadlock_on_sync_handle_calls(tmp_path):
    import libtorrent as lt
    from tests.daemon.common import torrent_dir

    ses = lt.session({
        "enable_dht": False,
        "enable_lsd": False,
        "enable_upnp": False,
        "enable_natpmp": False,
        "alert_mask": int(lt.alert.category_t.all_categories),
    })
    a = spritzle.daemon.alert.Alert()
    await a.start(ses)

    try:
        t1 = (torrent_dir / "testtorrent1.torrent").read_bytes()
        ti = lt.torrent_info(lt.bdecode(t1))
        h: Any = cast(Any, ses.add_torrent({"ti": ti, "save_path": str(tmp_path)}))

        for _ in range(200):
            ses.post_session_stats()
            tr = h.trackers()
            assert isinstance(tr, (list, tuple))
            st = h.status()
            assert st is not None
    finally:
        await a.stop()


