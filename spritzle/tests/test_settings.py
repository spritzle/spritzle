from spritzle.main import bootstrap
import spritzle.settings as settings

bootstrap()

def test_get_settings_session():
    s = settings.get_settings_session()
    assert isinstance(s, dict)
    assert len(s) > 0

def test_get_settings_proxy():
    s = settings.get_settings_proxy()
    assert isinstance(s, dict)
    assert len(s) > 0

def test_get_settings_pe():
    s = settings.get_settings_pe()
    assert isinstance(s, dict)
    assert len(s) > 0
