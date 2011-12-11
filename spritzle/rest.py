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

def route(path, method='GET', callback=None, **options):
    if callable(path): path, callback = None, path
    def deco(func):
        def wrapper(**urlargs):
            fmt = urlargs.pop('fmt') if 'fmt' in urlargs else 'json'

            # Handle older bottle versions
            try:
                urlargs.update(bottle.request.query)
            except AttributeError:
                urlargs.update(bottle.request.GET)

            if method in ('POST', 'PUT'):
                data = dispatch('decode_data', fmt, bottle.request.body)
                result = func(data, **urlargs)
            else:
                result = func(**urlargs)

            return dispatch('encode_data', fmt, result)
        bottle.route(path, method, wrapper, **options)
        bottle.route(path + '.:fmt', method, wrapper, **options)
        return func
    return deco(callback) if callback else deco

def get(path, callback=None, **options):
    return route(path, callback=callback, **options)

def delete(path, callback=None, **options):
    return route(path, method='DELETE', callback=callback, **options)

def post(path, callback=None, **options):
    return route(path, method='POST', callback=callback, **options)

def put(path, callback=None, **options):
    return route(path, method='PUT', callback=callback, **options)
