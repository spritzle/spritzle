from nose.tools import assert_raises

from spritzle.resource import user

def test_get_users():
    with assert_raises(NotImplementedError):
        user.get_users()

def test_create_user():
    with assert_raises(NotImplementedError):
        user.create_user('test')

def test_delete_user():
    with assert_raises(NotImplementedError):
        user.delete_user('test')

def test_get_user():
    with assert_raises(NotImplementedError):
        user.get_user('test')

def test_update_user():
    with assert_raises(NotImplementedError):
        user.update_user('test')
