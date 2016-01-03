from nose.tools import assert_raises

from spritzle.resource import config

def test_get_config():
    with assert_raises(NotImplementedError):
        config.get_config()

def test_update_config():
    with assert_raises(NotImplementedError):
        config.update_config()