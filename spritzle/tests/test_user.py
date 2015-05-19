from spritzle.main import bootstrap
from spritzle.user import users_view

bootstrap()

def test_users_view():
    assert [
        {'username': 'damoxc'},
        {'username': 'andar'},
        {'username': 'johnnyg'}
    ] == users_view()
