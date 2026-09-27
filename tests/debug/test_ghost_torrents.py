
import logging
from pathlib import Path
import os
import pytest
import libtorrent as lt
from spritzle.daemon.core import Core

# Reuse dummy torrent logic
def create_dummy_torrent(path: Path, name: str, size: int = 1024 * 1024):
    file_path = path / name
    file_path.write_bytes(os.urandom(size))
    entry = lt.create_file_entry(name, size)
    t = lt.create_torrent([entry])
    t.set_creator("Spritzle Check")
    lt.set_piece_hashes(t, str(path), lambda x: 0)
    torrent_path = path.parent / f"{name}.torrent"
    torrent_path.write_bytes(lt.bencode(t.generate()))
    return torrent_path

async def test_ghost_torrents(core, tmp_path):
    # Core is already started by fixture?
    if core.session is None:
        await core.start()
    
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger("spritzle.debug")
    
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # 1. Add a torrent
    name = "ghost_torrent"
    path = create_dummy_torrent(data_dir, name, size=1024)
    info = lt.torrent_info(str(path))
    from tests.daemon.common import add_test_torrent
    handle = add_test_torrent(core.session, info, save_path=str(tmp_path))
    
    # Populate torrent_data manually (simulate normal add)
    info_hash = str(handle.info_hash())
    core.torrent_data[info_hash] = {"spritzle.tags": ["test"]}
    
    assert len(core.session.get_torrents()) == 1
    assert info_hash in core.torrent_data
    
    # 2. Save session state
    # We want to force save session state, but DELETE the resume file
    await core.save_session_state()
    
    # Ensure resume data is also saved (usually)
    await core.resume_data.save_all()
    
    # 3. Corrupt state: Delete the .resume file
    resume_file = core.state_dir / f"{info_hash}.resume"
    if resume_file.exists():
        resume_file.unlink()
        log.info(f"Deleted resume file: {resume_file}")
    else:
        log.warning("Resume file not found!")
        
    # 4. Restart Core
    # Stop current core without saving again, to preserve our broken state (deleted resume file)
    await core.stop(save=False)
    
    log.info("Restarting core...")
    new_core = Core(core.config, core.state_dir)
    settings = {
        "enable_dht": False,
        "alert_mask": 0
    }
    
    # This calls load_session_state AND resume_data.load
    await new_core.start(settings)
    try:
        assert new_core.session is not None
        torrents = new_core.session.get_torrents()
        log.info(f"Torrents in session: {len(torrents)}")
        
        # If session.state restored it, count should be 1
        if len(torrents) == 1:
            log.info("Torrent restored from session state!")
            t_hash = str(torrents[0].info_hash())
            
            # Check if it is in torrent_data
            if t_hash in new_core.torrent_data:
                log.info("Torrent data successfully restored (empty) for ghost torrent.")
                assert new_core.torrent_data[t_hash] == {}
            else:
                log.error("FAILURE: Torrent in session but missing from torrent_data (Ghost Torrent)")
                pytest.fail("Ghost Torrent Detected - Consistency Check Failed")
        else:
            log.info("Torrent NOT restored from session state. (This is good)")
    finally:
        await new_core.stop()
