import spritzle.common as common

def test_struct_to_dict():
    class struct(object):
        a = 1
        b = 2
        __mytest__ = 3

    s = struct()

    d = common.struct_to_dict(s)

    assert isinstance(d, dict)
    assert d['a'] == 1
    assert d['b'] == 2
    assert '__mytest__' not in d
    assert len(d) == 2