from spritzle.main import bootstrap
import spritzle.settings as settings

bootstrap()

def test_get_settings_session():
    s = settings.get_settings_session()
    assert isinstance(s, dict)
    assert len(s) > 0

def test_put_settings_session():
    test_key = 'peer_connect_timeout'

    old = settings.get_settings_session()
    settings.put_settings_session({test_key: old[test_key] + 1})
    new = settings.get_settings_session()

    assert old[test_key] != new[test_key]
    assert old[test_key] == new[test_key] - 1

def test_get_settings_session_hps():
    s = settings.get_settings_session_hps()
    assert isinstance(s, dict)
    assert len(s) > 0

def test_get_settings_session_mmu():
    s = settings.get_settings_session_mmu()
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
