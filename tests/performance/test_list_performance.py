import time
import libtorrent as lt
from click.testing import CliRunner
from spritzle.cli.main import cli as spritzle_cli
from spritzle.daemon.keys import APP_KEY_CORE


def test_perf_spritzle_list_scaling(cli):
    """
    Benchmark spritzle list performance across varying numbers of torrents.
    """
    session = cli.app[APP_KEY_CORE].session
    runner = CliRunner()

    counts = [50, 100, 250, 500, 1000]
    print("\n" + "=" * 80)
    print("BENCHMARK: spritzle list scaling (Localhost Loopback)")
    print("=" * 80)
    current_count = 0

    for target in counts:
        for i in range(current_count + 1, target + 1):
            p = lt.parse_magnet_uri(f"magnet:?xt=urn:btih:{i:040x}&dn=torrent_{i}")
            p.save_path = "/tmp"
            session.add_torrent(p)
        current_count = target

        assert len(session.get_torrents()) == target

        # Measure 'spritzle list --plain'
        start_plain = time.perf_counter()
        res_plain = runner.invoke(spritzle_cli, ["list", "--plain"])
        elapsed_plain = time.perf_counter() - start_plain
        assert res_plain.exit_code == 0

        # Measure 'spritzle list --json'
        start_json = time.perf_counter()
        res_json = runner.invoke(spritzle_cli, ["list", "--json"])
        elapsed_json = time.perf_counter() - start_json
        assert res_json.exit_code == 0

        print(
            f"Torrents: {target:4d} | "
            f"Plain Table: {elapsed_plain:6.3f}s ({elapsed_plain/target*1000:5.2f}ms/t) | "
            f"JSON: {elapsed_json:6.3f}s ({elapsed_json/target*1000:5.2f}ms/t)"
        )


def test_perf_spritzle_list_breakdown(cli):
    """
    Profile the internal time breakdown of spritzle list:
    1. GET /torrent (info-hash index)
    2. N x GET /torrent/{id} (sequential per-torrent status fetch)
    3. Client formatting & rendering
    """
    session = cli.app[APP_KEY_CORE].session

    target = 500
    for i in range(1, target + 1):
        p = lt.parse_magnet_uri(f"magnet:?xt=urn:btih:{i:040x}&dn=torrent_{i}")
        p.save_path = "/tmp"
        session.add_torrent(p)

    assert len(session.get_torrents()) == target

    from spritzle.cli.main import Client
    client = Client()

    async def profile_phases(client):
        # Phase 1: Fetch hash list
        t0 = time.perf_counter()
        async with client.session.get(client.url("torrent")) as resp:
            hashes = await resp.json()
        t_index = time.perf_counter() - t0

        # Phase 2: Fetch each status sequentially (current CLI implementation)
        t0 = time.perf_counter()
        items = []
        total_bytes = 0
        for h in hashes:
            async with client.session.get(client.url(f"torrent/{h}")) as resp:
                raw = await resp.read()
                total_bytes += len(raw)
                import json
                items.append(json.loads(raw))
        t_individual = time.perf_counter() - t0

        # Phase 3: Format table
        t0 = time.perf_counter()
        from tabulate import tabulate
        field_list = ["name", "state", "progress", "download_rate", "upload_rate", "spritzle.tags"]
        table = [[item.get(f, "") for f in field_list] for item in items]
        _ = tabulate(table, headers=field_list, tablefmt="plain")
        t_render = time.perf_counter() - t0

        total_time = t_index + t_individual + t_render

        # Phase 4: Bulk single-request approach (Approach 1)
        t0 = time.perf_counter()
        async with client.session.get(
            client.url("torrent"),
            params={"keys": "name,state,progress,download_rate,upload_rate,spritzle.tags,errc,num_peers"},
        ) as resp:
            bulk_raw = await resp.read()
            import json
            bulk_items = json.loads(bulk_raw)
        t_bulk = time.perf_counter() - t0
        bulk_bytes = len(bulk_raw)

        print("\n" + "=" * 80)
        print("PROFILING BREAKDOWN: 500 torrents in session")
        print("=" * 80)
        print(f"1. Legacy GET /torrent (index): {t_index*1000:7.2f} ms ({t_index/total_time*100:5.1f}%) [1 HTTP request]")
        print(f"2. Legacy N x GET /torrent/<id>:{t_individual*1000:7.2f} ms ({t_individual/total_time*100:5.1f}%) [500 HTTP requests, {total_bytes/1024:.1f} KB]")
        print(f"3. Client rendering & format:   {t_render*1000:7.2f} ms ({t_render/total_time*100:5.1f}%)")
        print(f"Total Legacy Fetch + Render:    {total_time*1000:7.2f} ms (100.0%) [501 HTTP requests]")
        print("-" * 80)
        print("APPROACH 1: Bulk GET /torrent?keys=...")
        print(f"  Fetch duration:               {t_bulk*1000:7.2f} ms [1 HTTP request, {bulk_bytes/1024:.1f} KB]")
        print(f"  Total with Client Render:     {(t_bulk + t_render)*1000:7.2f} ms")
        print("-" * 80)
        print("IMPROVEMENT COMPARISON:")
        print(f"  - HTTP Requests:     501 requests -> 1 request ({501}x reduction)")
        print(f"  - Network Payload:   {total_bytes/1024:.1f} KB -> {bulk_bytes/1024:.1f} KB ({(1 - bulk_bytes/total_bytes)*100:.1f}% reduction)")
        print(f"  - Data Fetch Time:   {(t_index + t_individual)*1000:.2f} ms -> {t_bulk*1000:.2f} ms ({(t_index + t_individual)/t_bulk:.1f}x speedup)")
        print(f"  - End-to-End Time:   {total_time*1000:.2f} ms -> {(t_bulk + t_render)*1000:.2f} ms ({total_time/(t_bulk + t_render):.1f}x speedup)")
        print("=" * 80)

        assert len(bulk_items) == target
        assert len(items) == target

    client.do_command(profile_phases)

