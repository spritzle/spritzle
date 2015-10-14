from unittest.mock import patch, MagicMock
from nose.tools import assert_raises

import spritzle.main

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
