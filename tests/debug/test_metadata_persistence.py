
import logging
import os
from pathlib import Path
import time

import libtorrent as lt

from spritzle.daemon.core import Core

# Reuse dummy torrent creation logic
def create_dummy_torrent(path: Path, name: str, size: int = 1024 * 1024):
    file_path = path / name
    with open(file_path, "wb") as f:
        f.write(os.urandom(size))
    
    fs = lt.file_storage()
    fs.add_file(name, size)
    t = lt.create_torrent(fs)
    t.set_creator("Spritzle Benchmark")
    lt.set_piece_hashes(t, str(path), lambda x: 0)
    
    torrent_path = path.parent / f"{name}.torrent"
    with open(torrent_path, "wb") as f:
        f.write(lt.bencode(t.generate()))
    
    return torrent_path

async def test_metadata_persistence(cli, core, tmp_path):
    # This test verifies that metadata (spritzle.tags, etc) is correctly saved and loaded.
    # We suspect that with many torrents, the 5s timeout in save_all might cause data loss.
    
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger("spritzle.debug")
    NUM_TORRENTS = int(os.environ.get("SPRITZLE_METADATA_TORRENTS", 250)) # Enough to verify persistence across restart
    
    log.info(f"Generating {NUM_TORRENTS} dummy torrents...")
    torrent_files = []
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    for i in range(NUM_TORRENTS):
        p = create_dummy_torrent(data_dir, f"meta_{i}", size=1024)
        torrent_files.append(p)
        
    log.info("Adding torrents with metadata...")
    # We add metadata via the 'core.torrent_data' directly or via API to simulate tags
    # Let's use internal API for speed in setup
    
    import base64
    for i, p in enumerate(torrent_files):
        with open(p, "rb") as f:
            content = base64.b64encode(f.read()).decode("ascii")
        
        # Add via API to ensure full flow
        # We need to construct a valid request payload
        # Note: In real test, 'cli' is an aiohttp client. We need to await post.
        payload = {
            "file": content, 
            "flags": lt.torrent_flags.paused,
            "spritzle.tags": [f"tag_{i}"] 
        }
        resp = await cli.post("/torrent", json=payload)
        assert resp.status == 201

    # Verify metadata exists in memory
    assert len(core.torrent_data) == NUM_TORRENTS
    
    log.info("Stopping core (saving resume data)...")
    start_stop = time.monotonic()
    await core.stop()
    duration_stop = time.monotonic() - start_stop
    log.info(f"Core stopped in {duration_stop:.2f}s")
    
    # Check if resume files exist
    resume_files = list(core.state_dir.glob("*.resume"))
    log.info(f"Found {len(resume_files)} resume files on disk.")
    
    if len(resume_files) != NUM_TORRENTS:
        log.error(f"FAILURE: Expected {NUM_TORRENTS} resume files, found {len(resume_files)}")
    
    # Check content of one resume file to see if custom fields are there
    with open(resume_files[0], "rb") as f:
        data = lt.bdecode(f.read())
        assert b"spritzle.tags" in data
        # Custom fields are stored with key 'spritzle.tags' usually?
        # Let's check how resume_data.py saves it.
        # It updates the 'entry' with core.torrent_data[info_hash] items.
    
    # Restart core
    log.info("Restarting core...")
    new_core = Core(core.config, core.state_dir)
    settings = {
        "enable_upnp": False, 
        "enable_natpmp": False, 
        "enable_lsd": False, 
        "enable_dht": False,
        "anonymous_mode": True,
        "alert_mask": 0,
        "stop_tracker_timeout": 0,
    }
    await new_core.start(settings)
    
    assert new_core.session is not None
    log.info(f"Loaded {len(new_core.session.get_torrents())} torrents.")
    log.info(f"Loaded metadata for {len(new_core.torrent_data)} torrents.")
    
    assert len(new_core.torrent_data) == NUM_TORRENTS, "Missing metadata in memory after reload!"
    
    # Cleanup
    await new_core.stop()
