from spritzle import hooks

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
    
