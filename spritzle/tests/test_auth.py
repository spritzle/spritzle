from nose.tools import assert_raises

from spritzle.view import auth

def test_login():
    with assert_raises(NotImplementedError):
        auth.login()