from unittest.mock import patch, MagicMock
from nose.tools import assert_raises

import spritzle.main
from spritzle import hooks
from spritzle import error

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

def test_bootstrap():
    assert len(hooks._defaults) == 0
    spritzle.main.bootstrap()
    assert len(hooks._defaults) > 0

def test_main_class():
    main = spritzle.main.Main(12345)
    assert main.port == 12345

    with patch('spritzle.main.bottle.run'):
        main.start()
        spritzle.main.bottle.run.assert_called_once_with(
            port=12345,
            reloader=False,
            debug=False,
            server=spritzle.main.AiohttpServer
        )

def test_main_entry_point():
    with patch('spritzle.main.Main.start'):
        with patch('sys.argv'):
        
            spritzle.main.main()
            spritzle.main.Main.start.assert_called_once_with()

def test_hook_decode_data():
    data = '{"foo": "bar"}'
    d = spritzle.main.hook_decode_data('json', data)
    assert d == {'foo': 'bar'}

    with assert_raises(error.InvalidEncodingError):
        spritzle.main.hook_decode_data('foobar_data_type', data)

def test_hook_encode_data():
    d = {'foo': 'bar'}
    data = spritzle.main.hook_encode_data('json', d)
    assert data == '{"foo": "bar"}'

    with assert_raises(error.InvalidEncodingError):
        spritzle.main.hook_encode_data('foobar_data_type', d)