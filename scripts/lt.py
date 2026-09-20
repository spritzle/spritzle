import code
import libtorrent as lt

TORRENT = "../tests/daemon/torrents/testtorrent1.torrent"
with open(TORRENT, "rb") as f:
    ti = lt.torrent_info(lt.bdecode(f.read()))
s = lt.session({})
h = s.add_torrent({"ti": ti})
code.interact(local=locals())
