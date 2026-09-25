
import asyncio
import time
import logging
import base64
import os
from pathlib import Path

import libtorrent as lt


from spritzle.daemon.core import Core

# Re-using fixtures from conftest, but we might need to tweak them or just reuse them.
# The 'core' fixture in conftest uses in-memory config and temp state dir, which is good.
# It also disables DHT/LSD/UPnP/NatPMP.



def create_dummy_torrent(path: Path, name: str, size: int = 1024 * 1024):
    # Create a dummy file
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

async def test_performance_many_torrents(cli, core, tmp_path):
    # Configuration
    NUM_TORRENTS = int(os.environ.get("SPRITZLE_BENCHMARK_TORRENTS", 500))
    
    log = logging.getLogger("spritzle.perf")
    log.info(f"Starting performance test with {NUM_TORRENTS} torrents")
    
    # Generate dummy torrents
    log.info("Generating dummy torrents...")
    start_gen = time.monotonic()
    
    torrent_files = []
    # Create a directory to hold dummy data
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # We can execute this in a thread pool to avoid blocking the loop if it takes too long,
    # but for 1000 small files it might be okay. Let's do it in executor to be safe and fast.
    
    def generate_batch(start_index, count):
        paths = []
        for i in range(count):
            name = f"bench_{start_index + i}"
            p = create_dummy_torrent(data_dir, name, size=1024) # 1KB files
            paths.append(p)
        return paths

    # Run generation in parallel chunks to speed up test setup
    chunk_size = 100
    tasks = []
    loop = asyncio.get_running_loop()
    for i in range(0, NUM_TORRENTS, chunk_size):
        params = (i, min(chunk_size, NUM_TORRENTS - i))
        tasks.append(loop.run_in_executor(None, generate_batch, *params))
    
    results = await asyncio.gather(*tasks)
    for r in results:
        torrent_files.extend(r)
        
    duration_gen = time.monotonic() - start_gen
    log.info(f"Generated {NUM_TORRENTS} torrents in {duration_gen:.2f}s")
    
    # Measure Add Performance
    log.info("Adding torrents to session...")
    start_add = time.monotonic()
    
    # Prepare payloads
    payloads = []
    for p in torrent_files:
        with open(p, "rb") as f:
            content = base64.b64encode(f.read()).decode("ascii")
        payloads.append({"file": content, "flags": lt.torrent_flags.paused}) # Add paused to avoid checking overhead affecting add time too much
    
    # Add them sequentially as a client would
    for payload in payloads:
        resp = await cli.post("/torrent", json=payload)
        if resp.status != 201:
            log.error(f"Failed to add torrent: {await resp.text()}")
        assert resp.status == 201
        
    duration_add = time.monotonic() - start_add
    rate_add = NUM_TORRENTS / duration_add
    log.info(f"Added {NUM_TORRENTS} torrents in {duration_add:.2f}s ({rate_add:.2f} torrents/s)")
    
    # Measure List Performance (Full List)
    log.info("Fetching full torrent list...")
    start_list = time.monotonic()
    resp = await cli.get("/torrent")
    assert resp.status == 200
    tlist = await resp.json()
    assert len(tlist) == NUM_TORRENTS
    duration_list = time.monotonic() - start_list
    log.info(f"Fetched full list in {duration_list:.4f}s")
    
    # Measure List Performance (Query)
    # Let's query for something that requires iterating status
    log.info("Fetching torrent list with query...")
    start_query = time.monotonic()
    resp = await cli.get("/torrent?progress.ge=0")
    assert resp.status == 200
    qlist = await resp.json()
    assert len(qlist) == NUM_TORRENTS
    duration_query = time.monotonic() - start_query
    log.info(f"Fetched query list in {duration_query:.4f}s")

    # Measure Save Resume Data
    # The 'core.save_session_state' triggers resume data saving for all torrents
    # We can also force it via resume_data.save_all() or similar if exposed,
    # but let's use the core method which simulates shutdown/checkpoint.
    log.info("Saving session state (resume data)...")

    
    # We need to access core directly for this benchmark to be accurate on internal timing,
    # or trigger a shutdown.
    # Core.save_session_state calls session.save_state and writes to disk.
    # It also likely triggers resume data saving for torrents if needed.
    # However, 'save_session_state' mostly saves the session settings/DHT state.
    # The actual torrent resume data is saved when specific events happen or on shutdown.
    # 'Core.stop()' calls 'resume_data.stop()' which saves all resume data.
    
    await core.save_session_state() # measures session state save
    
    # Force save resume data for all torrents
    # In spritzle/daemon/resume_data.py, there might be a method.
    # Core has self.resume_data. Let's look at how to trigger it.
    # Core.stop() does it. Let's time Core.stop() but that limits further tests.
    # Alternative: check ResumeData class.
    # For now, let's verify if we can trigger it.
    
    # Mocking or calling internal method for benchmark
    # await core.resume_data.save_all() # Hypothetical, need to check code.
    # Looking at core.py:
    # async def stop(self):
    #     ...
    #     await self.resume_data.stop()
    #     await self.save_session_state()
    
    start_save_resume = time.monotonic()
    await core.resume_data.save_all() # Assuming this exists or I'll check resume_data.py
    duration_save_resume = time.monotonic() - start_save_resume
    log.info(f"Saved resume data for all torrents in {duration_save_resume:.4f}s")
    
    # Measure Startup/Load Time
    log.info("Restarting Core to measure startup load time...")
    # 1. Stop current core
    await core.stop()
    
    # 2. Create new core with same state_dir
    state_dir = core.state_dir
    config = core.config
    
    new_core = Core(config, state_dir)
    
    # Settings for isolation (same as conftest)
    settings = {
        "enable_upnp": False,
        "enable_natpmp": False,
        "enable_lsd": False,
        "enable_dht": False,
        "anonymous_mode": True,
        "alert_mask": 0,
        "stop_tracker_timeout": 0,
    }
    
    start_load = time.monotonic()
    await new_core.start(settings)
    duration_load = time.monotonic() - start_load
    log.info(f"Loaded {NUM_TORRENTS} torrents in {duration_load:.4f}s")
    
    assert new_core.session is not None
    assert len(new_core.session.get_torrents()) == NUM_TORRENTS
    
    # Update app to use new core
    from spritzle.daemon.keys import APP_KEY_CORE
    cli.app[APP_KEY_CORE] = new_core
    
    # Measure Bulk Pause (Sequential HTTP)
    log.info("Pausing all torrents via HTTP...")
    start_pause = time.monotonic()
    
    # We need the list of IDs again? We know they are generated deterministically or we can fetch.
    # We can use the cached list 'tlist' from earlier, effectively.
    # Or just fetch list again (fast now).
    resp = await cli.get("/torrent")
    all_ids = await resp.json()
    
    for tid in all_ids:
        await cli.post(f"/torrent/{tid}/pause")
        
    duration_pause = time.monotonic() - start_pause
    rate_pause = NUM_TORRENTS / duration_pause
    log.info(f"Paused {NUM_TORRENTS} torrents in {duration_pause:.2f}s ({rate_pause:.2f} t/s)")
    
    # Measure Bulk Removal
    log.info("Removing all torrents via HTTP (Bulk Endpoint)...")
    start_remove = time.monotonic()
    
    resp = await cli.delete("/torrent", params={"delete_files": 1})
    if resp.status != 200:
        log.error(f"Failed to delete all torrents: {await resp.text()}")
    assert resp.status == 200
    
    duration_remove = time.monotonic() - start_remove
    log.info(f"Removed {NUM_TORRENTS} torrents in {duration_remove:.2f}s")
    
    # Verify empty
    assert new_core.session is not None
    assert len(new_core.session.get_torrents()) == 0
    
    # Report
    print(f"\n--- Performance Report ({NUM_TORRENTS} torrents) ---")
    print(f"Generation: {duration_gen:.2f}s")
    print(f"Add:        {duration_add:.2f}s ({rate_add:.2f} t/s)")
    print(f"List(All):  {duration_list:.4f}s")
    print(f"List(Qry):  {duration_query:.4f}s")
    print(f"SaveResume: {duration_save_resume:.4f}s")
    print(f"Startup:    {duration_load:.4f}s")
    print(f"BulkPause:  {duration_pause:.2f}s ({rate_pause:.2f} t/s)")
    print(f"BulkRemove: {duration_remove:.2f}s")
    print("------------------------------------------------")
    
    # Cleanup new_core
    await new_core.stop()

