#
# spritzle/rest.py
#
# Copyright (C) 2011 Damien Churchill <damoxc@gmail.com>
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

import bottle

from spritzle.hooks import dispatch

def get(path, callback=None, **options):
    if callable(path): path, callback = None, path

    def deco(func):
        def wrapper(fmt=None):
            fmt = 'json' if fmt is None else fmt
            result = func()
            return dispatch('encode_data', fmt, result)
        bottle.get(path, callback=wrapper, **options)
        return func

    return deco(callback) if callback else deco

def delete(path, callback=None, **options):
    if callable(path): path, callback = None, path

    def deco(func):
        def wrapper(fmt=None):
            fmt = 'json' if fmt is None else fmt
            data = dispatch('decode_data', fmt, request.body)
            result = callback(data)
            return dispatch('encode_data', fmt, result)
        bottle.post(path, callback=wrapper, **options)
        return func

    return deco(callback) if callback else deco

def post(path, callback=None, **options):
    if callable(path): path, callback = None, path

    def deco(func):
        def wrapper(fmt=None):
            fmt = 'json' if fmt is None else fmt
            data = dispatch('decode_data', fmt, request.body)
            result = callback(data)
            return dispatch('encode_data', fmt, result)
        bottle.post(path, callback=wrapper, **options)
        return func

    return deco(callback) if callback else deco

def put(path, callback=None, **options):
    if callable(path): path, callback = None, path

    def deco(func):
        def wrapper(fmt=None):
            fmt = 'json' if fmt is None else fmt
            data = dispatch('decode_data', fmt, request.body)
            result = callback(data)
            return dispatch('encode_data', fmt, result)
        bottle.post(path, callback=wrapper, **options)
        return func

    return deco(callback) if callback else deco
