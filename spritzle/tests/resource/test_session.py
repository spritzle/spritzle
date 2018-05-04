#
# test_session.py
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


async def test_get_session_stats(cli):
    response = await cli.get('/session/stats')
    s = await response.json()
    assert isinstance(s, dict)
    assert len(s) > 0


async def test_get_session_dht(cli):
    response = await cli.get('/session/dht')
    b = await response.json()
    assert isinstance(b, bool)


async def test_get_settings(cli):
    response = await cli.get('/session/settings')
    s = await response.json()
    assert isinstance(s, dict)
    assert len(s) > 0


async def test_put_settings(cli):
    response = await cli.get('/session/settings')
    old = await response.json()
    test_key = 'peer_connect_timeout'

    response = await cli.put('/session/settings',
                             json={test_key: old[test_key] + 1})
    assert response.status == 200

    response = await cli.get('/session/settings')
    new = await response.json()

    assert old[test_key] != new[test_key]
    assert old[test_key] == new[test_key] - 1


async def test_put_settings_bad_key(cli):
    response = await cli.put('/session/settings', json={'bad_key': 1})
    assert response.status == 400


async def test_put_settings_type_coercion(cli):
    response = await cli.put('/session/settings', json={'peer_connect_timeout': '1'})
    assert response.status == 200
