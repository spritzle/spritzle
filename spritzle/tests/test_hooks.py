from spritzle import hooks
from spritzle import error
from nose.tools import assert_raises

def test_register_default():
    test_args = ["foo", 1, {"bar": 2, "baz": 5.4}]
    
    global called
    called = False

    def handler(*args, **kwargs):
        assert args[0] == test_args
        global called
        called = True

        return
        
    hooks.register_default("foobar", handler)
    
    hooks.dispatch("foobar", test_args)
    assert called == True

def test_register():
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

    with assert_raises(error.InvalidHook):
        hooks.register("test_hook", handler)
        
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
    
