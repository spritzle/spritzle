#
# test_hooks.py
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

from spritzle import hooks
from spritzle import error
from nose.tools import assert_raises, with_setup

old_defaults = {}
old_handlers = {}

def setup_module():
    old_defaults = hooks._defaults
    hooks._defaults = {}

    old_handlers = hooks._handlers
    hooks._handlers = {}

def teardown_module():
    hooks._defaults = old_defaults
    hooks._handlers = old_handlers

def setup():
    hooks._defaults = {}
    hooks._handlers = {}

@with_setup(setup)
def test_register_default():
    assert "test_hook" not in hooks._defaults
    hooks.register_default("test_hook", None)
    assert "test_hook" in hooks._defaults

@with_setup(setup)
def test_register():
    assert "test_hook" not in hooks._handlers
    assert "test_hook" not in hooks._defaults

    with assert_raises(error.InvalidHook):
        hooks.register("test_hook", lambda x: x)

    assert "test_hook" not in hooks._handlers
    assert "test_hook" not in hooks._defaults
    
    hooks.register_default("test_hook", lambda x: x)
    
    hooks.register("test_hook", lambda x: x)
    
    assert "test_hook" in hooks._handlers

@with_setup(setup)
def test_dispatch():
    global called_default
    called_default = False
    def handler_default(*args, **kwargs):
        global called_default
        called_default = True
        return

    global called
    called = False
    def handler(*args, **kwargs):
        global called
        called = True
        return args[0]

       
    hooks.register_default("test_hook", handler_default)
    hooks.register("test_hook", handler)

    hooks.dispatch("test_hook", 1)
    assert called_default == False
    assert called == True
    called_default = False
    called = False
    hooks.dispatch("test_hook", None)
    assert called_default == True
    assert called == True
