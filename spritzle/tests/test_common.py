import binascii
import libtorrent as lt
import spritzle.common as common

def test_struct_to_dict():
    class struct(object):
        a = 1
        b = 2
        __mytest__ = 3
        sha1_hash = lt.sha1_hash(binascii.unhexlify('a0'*20))

    s = struct()

    d = common.struct_to_dict(s)

    assert isinstance(d, dict)
    assert d['a'] == 1
    assert d['b'] == 2
    assert '__mytest__' not in d
    assert len(d) == 3
    assert d['sha1_hash'] == 'a0'*20

def test_update_struct_with_dict():
    class struct(object):
        a = 1
        b = 2

    s = struct()
    d = {'a': 3, 'c': 1}

    s = common.update_struct_with_dict(s, d)

    assert s.a == 3
    assert s.b == 2
    assert hasattr(s, 'c') == False