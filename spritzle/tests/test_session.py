from spritzle.main import bootstrap
from spritzle.view import session

bootstrap()

def test_session_status():
    s = session.get_session_status()
    assert isinstance(s, dict)
    assert len(s) > 0