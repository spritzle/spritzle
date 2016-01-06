from spritzle.main import bootstrap
from spritzle.resource import session

bootstrap()

def test_get_session_status():
    s = session.get_session_status()
    assert isinstance(s, dict)
    assert len(s) > 0

def test_get_session_cache_status():
    s = session.get_session_cache_status()
    assert isinstance(s, dict)
    assert len(s) > 0

def test_get_dht():
    b = session.get_dht()
    assert b == False

def test_put_dht():
    session.put_dht()
    b = session.get_dht()
    assert b == True

def test_delete_dht():
    session.delete_dht()
    b = session.get_dht()
    assert b == False
