from spritzle import hooks
from spritzle import error
from nose.tools import assert_raises, with_setup

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
