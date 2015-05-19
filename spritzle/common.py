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


def struct_to_dict(struct):
    """
    Convert a libtorrent struct into a dictionary by finding all
    attributes that do not start with '_'.

    """
    d = {}
    keys = [x for x in dir(struct) if not x.startswith('_')]

    for key in keys:
        try:
            d[key] = getattr(struct, key)
        except TypeError as e:
            pass

    return d