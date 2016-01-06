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

from spritzle.main import bootstrap
from spritzle.resource import session

bootstrap()

def test_get_session_status():
    s = session.get_session_status()
    assert isinstance(s, dict)
    assert len(s) > 0

def test_get_session_cache_status():
    s = session.get_session_cache_status()
    assert isinstance(s, dict)
    assert len(s) > 0

def test_get_dht():
    b = session.get_dht()
    assert b == False

def test_put_dht():
    session.put_dht()
    b = session.get_dht()
    assert b == True

def test_delete_dht():
    session.delete_dht()
    b = session.get_dht()
    assert b == False
