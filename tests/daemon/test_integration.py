import asyncio
import os
import shutil
import tempfile
from pathlib import Path

import libtorrent as lt
import pytest


from spritzle.daemon.config import Config
from spritzle.daemon.core import Core


@pytest.fixture
def create_core(loop):
    tmp_dirs = []

    def _create_core():
        config_dir = Path(tempfile.mkdtemp(prefix="spritzle-test-config"))
        tmp_dirs.append(config_dir)
        state_dir = Path(tempfile.mkdtemp(prefix="spritzle-test-state"))
        tmp_dirs.append(state_dir)

        # Create hooks directory
        hooks_dir = config_dir / "hooks"
        hooks_dir.mkdir()

        config = Config(in_memory=True, config_dir=str(config_dir))
        core = Core(config, state_dir)

        settings = {
            "enable_upnp": False,
            "enable_natpmp": False,
            "enable_lsd": False,
            "enable_dht": False,
            "anonymous_mode": False,  # Allow direct connections
            "alert_mask": lt.alert.category_t.all_categories,
            "listen_interfaces": "127.0.0.1:0",
            "allow_multiple_connections_per_ip": True,
        }

        return core, settings, config_dir

    yield _create_core

    for d in tmp_dirs:
        shutil.rmtree(str(d), ignore_errors=True)


async def test_torrent_transfer(create_core, loop):
    # Setup Seeder
    seeder_core, seeder_settings, _ = create_core()
    await seeder_core.start(seeder_settings)

    # Setup Leecher
    leecher_core, leecher_settings, _ = create_core()
    await leecher_core.start(leecher_settings)

    try:
        # Create test data
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            data_file = tmp_path / "testdata.bin"
            # 1MB of random data
            data = os.urandom(1024 * 1024)
            data_file.write_bytes(data)

            # Create torrent
            entry = lt.create_file_entry(data_file.name, len(data))
            t = lt.create_torrent([entry])
            t.set_creator("libtorrent %s" % lt.__version__)
            t.set_comment("Test")
            lt.set_piece_hashes(t, str(tmp_path))
            torrent_bytes = t.generate()

            # Save torrent file
            torrent_file = tmp_path / "test.torrent"
            torrent_file.write_bytes(lt.bencode(torrent_bytes))

            ti = lt.torrent_info(str(torrent_file))

            # Add to seeder
            from tests.daemon.common import add_test_torrent
            seeder_handle = add_test_torrent(
                seeder_core.session,
                ti,
                save_path=str(tmp_path),
                flags=lt.torrent_flags.seed_mode,
            )

            # Wait for seeder to be checked/ready
            while not seeder_handle.status().is_seeding:
                await asyncio.sleep(0.1)

            # Add to leecher
            # Use a different download directory
            with tempfile.TemporaryDirectory() as dl_dir:
                leecher_handle = add_test_torrent(
                    leecher_core.session,
                    ti,
                    save_path=str(dl_dir),
                )

                # Connect peers
                seeder_port = seeder_core.session.listen_port()
                print(f"Seeder listening on {seeder_port}")

                # Add seeder as peer to leecher
                leecher_handle.connect_peer(("127.0.0.1", seeder_port))

                # Wait for download
                print("WAITING FOR DOWNLOAD")
                for i in range(200):  # 20 seconds timeout
                    s = leecher_handle.status()
                    if s.is_seeding:
                        print("LEECHER IS SEEDING")
                        break
                    if i % 10 == 0:
                        print(f"WAITING... {i} status={s.state} p={s.progress}")
                    await asyncio.sleep(0.1)

                assert leecher_handle.status().is_seeding

                # Verify data
                downloaded_file = Path(dl_dir) / "testdata.bin"
                assert downloaded_file.exists()
                assert downloaded_file.read_bytes() == data

    finally:
        await seeder_core.stop()
        await leecher_core.stop()


async def test_hook_integration(create_core, loop):
    core, settings, config_dir = create_core()

    # Create a hook script
    hooks_dir = config_dir / "hooks"
    # We will trigger a pause, so we expect torrent_paused
    hook_script = hooks_dir / "torrent_paused"

    token_file = config_dir / "hook_triggered"

    script_content = f"""#!/bin/sh
echo "Hook Triggered" > "{token_file}"
"""
    hook_script.write_text(script_content)
    hook_script.chmod(0o755)

    await core.start(settings)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a real dummy torrent
            dummy = Path(tmpdir) / "dummy.txt"
            dummy.write_text("Hello World")
            entry = lt.create_file_entry(dummy.name, dummy.stat().st_size)
            t = lt.create_torrent([entry])
            lt.set_piece_hashes(t, str(tmpdir))

            ti = lt.torrent_info(t.generate())

            from tests.daemon.common import add_test_torrent
            handle = add_test_torrent(core.session, ti, save_path=str(tmpdir))

            # Wait a bit
            await asyncio.sleep(0.5)

            # Force an event: pause
            handle.pause()

            # Poll for token file
            for _ in range(50):
                if token_file.exists():
                    break
                await asyncio.sleep(0.1)

            assert token_file.exists(), (
                f"Hook script {hook_script} should have created {token_file}"
            )

    finally:
        await core.stop()
