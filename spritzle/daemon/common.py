#
# spritzle/common.py
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

import datetime
import libtorrent as lt
import logging

log = logging.getLogger('spritzle')


def struct_to_dict(struct, ignore_keys=None):
    """
    Convert a libtorrent struct into a dictionary by finding all
    attributes that do not start with '_'.

    A conversion attempt will be made for special libtorrent types.
    """
    # Define converter functions to coerce libtorrent types into
    # basic objects.
    def lt_sha1_hash(value):
        return str(value)

    def datetime_timedelta(value):
        return str(value.total_seconds())

    def enum(value):
        return value.name

    def error_code(value):
        return {
            'value': value.value(),
            'message': value.message(),
            'category': {
                'name': value.category().name(),
                'message': value.category().message(value.value()),
            },
        }

    type_converters = {
        lt.sha1_hash: lt_sha1_hash,
        datetime.timedelta: datetime_timedelta,
        lt.torrent_status.states: enum,
        lt.error_code: error_code,
    }

    d = {}
    keys = [x for x in dir(struct) if not x.startswith('_')]

    for key in keys:
        if ignore_keys and key in ignore_keys:
            continue

        value = getattr(struct, key)
        vtype = type(value)

        # Convert the value if necessary
        if vtype in type_converters:
            value = type_converters[vtype](value)

        # Skip values that cannot be json encoded
        if (type(value) not in (dict, list, str, int, float, bool) and
                value is not None):
            log.debug(
                f'skipping key: {key} type: {type(value)} value: {value}')
            continue

        d[key] = value

    return d


def update_struct_with_dict(struct, dictionary):
    """
    Update a struct with items from a dictionary.  Will only
    update existing attributes; will not set new ones.
    """

    for key, value in dictionary.items():
        if hasattr(struct, key):
            setattr(struct, key, value)
    return struct
