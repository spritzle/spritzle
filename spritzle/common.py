#
# spritzle/common.py
#
# Copyright (C) 2015 Andrew Resch <andrewresch@gmail.com>
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

import libtorrent as lt

def struct_to_dict(struct):
    """
    Convert a libtorrent struct into a dictionary by finding all
    attributes that do not start with '_'.

    A conversion attempt will be made for special libtorrent types.
    """

    # Define converter functions to coerce libtorrent types into
    # basic objects.
    def lt_sha1_hash(value):
        return str(value)

    type_converters = {
        lt.sha1_hash: lt_sha1_hash,
    }

    d = {}
    keys = [x for x in dir(struct) if not x.startswith('_')]

    for key in keys:
        try:
            value = getattr(struct, key)

            # Convert the value if necessary
            if type(value) in type_converters:
                value = type_converters[type(value)](value)

            d[key] = value
        except TypeError as e:
            pass

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
