#
# spritzle/settings.py
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

from bottle import delete, get, post, put
from spritzle.core import core
import spritzle.common as common

import libtorrent

@get('/settings/session')
def get_settings_session():
    return common.struct_to_dict(core.session.settings())

@put('/settings/session')
def put_settings_session(settings):
    s = common.update_struct_with_dict(core.session.settings(), settings)
    core.session.set_settings(s)

@get('/settings/session/high_performance_seed')
def get_settings_session_hps():
    return common.struct_to_dict(libtorrent.high_performance_seed())

@get('/settings/session/min_memory_usage')
def get_settings_session_mmu():
    return common.struct_to_dict(libtorrent.min_memory_usage())

@get('/settings/proxy')
def get_settings_proxy():
    return common.struct_to_dict(core.session.proxy())

@put('/settings/proxy')
def put_settings_proxy(settings):
    s = common.update_struct_with_dict(core.session.proxy(), settings)
    core.session.set_proxy(s)

@get('/settings/pe')
def get_settings_pe():
    return common.struct_to_dict(core.session.get_pe_settings())

@get('/settings/dht')
def get_settings_dht():
    return common.struct_to_dict(core.session.get_dht_settings())

@put('/settings/dht')
def put_settings_dht(settings):
    s = common.update_struct_with_dict(core.session.get_dht_settings(), settings)
    core.session.set_dht_settings(s)