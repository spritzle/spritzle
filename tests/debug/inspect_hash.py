
import libtorrent as lt
import os
import sys
import time
import shutil
from pathlib import Path

def main():
    print(f"Libtorrent version: {lt.version}")
    tmp = Path("hash_debug")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()

    # Create dummy torrent
    print("Creating dummy torrent...")
    path = tmp / "test_file"
    with open(path, "wb") as f:
        f.write(os.urandom(1024))
    
    fs = lt.file_storage()
    fs.add_file("test_file", 1024)
    t = lt.create_torrent(fs)
    lt.set_piece_hashes(t, str(tmp), lambda x: 0)
    torrent_path = tmp / "test.torrent"
    with open(torrent_path, "wb") as f:
        f.write(lt.bencode(t.generate()))

    # Load torrent_info
    ti = lt.torrent_info(str(torrent_path))
    print(f"Torrent File Info Hash: {ti.info_hash()}")

    # Start session
    ses = lt.session()
    print("Session started.")
    
    # Add torrent
    atp = {"ti": ti, "save_path": str(tmp)}
    h = ses.add_torrent(atp)
    print(f"Handle Info Hash: {h.info_hash()}")

    # Wait for checking
    while not h.status().is_seeding:
        time.sleep(0.1)

    # Save resume data
    print("Saving resume data...")
    h.save_resume_data()
    
    # Wait for alert
    alert = None
    while alert is None:
        if not ses.wait_for_alert(1000):
            continue
        for a in ses.pop_alerts():
            if isinstance(a, lt.save_resume_data_alert):
                alert = a
                break
    
    print("Got save_resume_data_alert.")
    r = lt.write_resume_data(alert.params)
    
    # Check info-hash in resume data
    if b"info-hash" in r:
        import binascii
        r_hash = binascii.hexlify(r[b"info-hash"]).decode()
        print(f"Resume Data 'info-hash': {r_hash}")
    else:
        print("Resume Data missing 'info-hash' key!")
        # Print keys
        print(f"Keys: {list(r.keys())}")

    # Cleanup
    del ses
    shutil.rmtree(tmp)

if __name__ == "__main__":
    main()
