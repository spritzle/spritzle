import json

from spritzle.core import bootstrap
from spritzle.user import users_view

bootstrap()

def test_users_view():
    data = json.dumps([
        {'username': 'damoxc'},
        {'username': 'andar'},
        {'username': 'johnnyg'}
    ])
    assert data == users_view()

def test_users_view_invalid_encoding():
    assert users_view('invalid') == None
