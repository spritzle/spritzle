#
# spritzle/session.py
#
# Copyright (C) 2011 Andrew Resch <andrewresch@gmail.com>
#               2011 Damien Churchill <damoxc@gmail.com>
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

from spritzle.rest import delete, get, post, put
from spritzle.core import core

@get('/session')
def get_session(fmt=None):
    status = {}
    session_status = core.session.status()
    keys = [x for x in dir(session_status) if not x.startswith('_')]

    for key in keys:
        try:
            status[key] = getattr(session_status, key)
        except TypeError as e:
            print("Unsupported libtorrent key: ", key)

    return status

@put('/session')
def update_session(fmt=None):
    raise NotImplementedError
