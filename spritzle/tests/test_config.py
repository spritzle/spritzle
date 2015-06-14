from spritzle.config import Config

import tempfile
import os
import shutil
import json

def test_config_init_no_dir():
    tmpdir = os.path.join(tempfile.gettempdir(), 'spritzletmpdir')
    home = os.environ['HOME']
    os.environ['HOME'] = tmpdir

    c = Config()

    os.environ['HOME'] = home

    assert c.file == os.path.join(
        tmpdir, '.config', 'spritzle', 'spritzle.conf')

    assert os.path.isfile(
        os.path.join(
            tmpdir, '.config', 'spritzle', 'spritzle.conf')) == True

    shutil.rmtree(tmpdir)

def test_config_init_with_dir():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)

def test_config_save():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c.save()
        old = c.config
        c.load()
        assert old == c.config

def test_config_load():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c['foo'] = 1
        old = c.config
        c.load()
        assert c.config == old

def test_on_modified_load():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c['foo'] = 1
        json.dump({'foo': 2}, open(c.file, 'w'))
        c.notifier.handle_read()
        assert c['foo'] == 2

def test_contains():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c['foo'] = 1
        assert 'foo' in c

def test_delitem():
    with tempfile.TemporaryDirectory() as tempdir:
        c = Config(config_dir=tempdir)
        c['foo'] = 1
        del c['foo']
        assert 'foo' not in c
