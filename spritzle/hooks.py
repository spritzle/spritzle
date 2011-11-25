#
# spritzle/hooks.py
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

_defaults = {}
_handlers = {}

def dispatch(hook_name, *args):
    if hook_name in _handlers:
        for handler in _handlers[hook_name]:
            result = handler(*args)
            if result is None:
                continue
            return result

    if hook_name in _defaults:
        return _defaults[hook_name](*args)

def register(hook_name, handler):
    handlers = _hooks.setdefault(hook_name, [])
    handlers.append(handler)

def register_default(hook_name, handler):
    _defaults[hook_name] = handler
