import os
torrent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'torrents')
from unittest.mock import patch, MagicMock

import libtorrent as lt
import bottle

from spritzle.main import bootstrap
from spritzle.view import torrent

bootstrap()

def test_get_torrent():
    test_add_torrent()

    torrents = torrent.get_torrent()
    assert isinstance(torrents, list)
    assert len(torrents) > 0

    ts = torrent.get_torrent('44a040be6d74d8d290cd20128788864cbf770719')
    assert isinstance(ts, dict)
    assert ts['info_hash'] == '44a040be6d74d8d290cd20128788864cbf770719'

def test_add_torrent():

    files = {
        'random_one_file': bottle.FileUpload(
            open(os.path.join(torrent_dir, 'random_one_file.torrent'), 'rb'),
            'random_one_file.torrent',
            'random_one_file.torrent'
        )
    }

    request = MagicMock()
    request.files = files
    request.forms = {
        'ti': None,
        'paused': True,
    }

    with patch('bottle.request', request):
        info_hash = torrent.add_torrent()['info_hash']
        assert info_hash == '44a040be6d74d8d290cd20128788864cbf770719'
        assert torrent.get_torrent() == ['44a040be6d74d8d290cd20128788864cbf770719']