import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from spritzle.cli.display import strip_ansi
from spritzle.cli.dashboard import (
    DashboardState,
    FilterTab,
    KeyPressWatcher,
    _sleep_or_quit,
    build_dashboard_renderable,
    execute_command,
    fetch_session_stats,
    fetch_torrent_data,
    fetch_torrent_detail,
    fetch_torrent_files,
    fetch_torrent_peers,
    fetch_torrent_trackers,
    fetch_torrents_with_status,
    handle_key_input,
    parse_keys_from_bytes,
    render_single_watch_panel,
    run_dashboard,
    watch_single_torrent,
)


def test_parse_keys_from_bytes_standard():
    assert parse_keys_from_bytes(b"q") == ["q"]
    assert parse_keys_from_bytes(b"Q") == ["Q"]
    assert parse_keys_from_bytes(b" ") == [" "]
    assert parse_keys_from_bytes(b":") == [":"]
    assert parse_keys_from_bytes(b"/") == ["/"]
    assert parse_keys_from_bytes(b"\r") == ["enter"]
    assert parse_keys_from_bytes(b"\n") == ["enter"]
    assert parse_keys_from_bytes(b"\x7f") == ["backspace"]
    assert parse_keys_from_bytes(b"\x08") == ["backspace"]
    assert parse_keys_from_bytes(b"\t") == ["tab"]
    assert parse_keys_from_bytes(b"\x1b") == ["escape"]
    assert parse_keys_from_bytes(b"\x03") == ["ctrl_c"]
    assert parse_keys_from_bytes(b"\x04") == ["ctrl_d"]


def test_parse_keys_from_bytes_escape_sequences():
    # Arrow keys
    assert parse_keys_from_bytes(b"\x1b[A") == ["up"]
    assert parse_keys_from_bytes(b"\x1b[B") == ["down"]
    assert parse_keys_from_bytes(b"\x1b[C") == ["right"]
    assert parse_keys_from_bytes(b"\x1b[D") == ["left"]
    assert parse_keys_from_bytes(b"\x1bOA") == ["up"]
    assert parse_keys_from_bytes(b"\x1bOB") == ["down"]

    # Navigation & control keys
    assert parse_keys_from_bytes(b"\x1b[5~") == ["page_up"]
    assert parse_keys_from_bytes(b"\x1b[6~") == ["page_down"]
    assert parse_keys_from_bytes(b"\x1b[3~") == ["delete"]
    assert parse_keys_from_bytes(b"\x1b[1~") == ["home"]
    assert parse_keys_from_bytes(b"\x1b[4~") == ["end"]
    assert parse_keys_from_bytes(b"\x1b[H") == ["home"]
    assert parse_keys_from_bytes(b"\x1b[F") == ["end"]
    assert parse_keys_from_bytes(b"\x1b[Z") == ["shift_tab"]

    # Stream of multiple keys
    stream = b"\x1b[A\x1b[Bq"
    assert parse_keys_from_bytes(stream) == ["up", "down", "q"]


@pytest.fixture
def sample_torrents():
    return [
        {
            "name": "archlinux-2026.09.01-x86_64.iso",
            "info_hash": "a" * 40,
            "state": "downloading",
            "progress": 0.45,
            "download_rate": 2048000,
            "upload_rate": 102400,
            "total_wanted": 1000000000,
            "total_size": 1000000000,
            "total_done": 450000000,
            "all_time_upload": 1024000,
            "all_time_download": 450000000,
            "num_peers": 15,
            "num_seeds": 5,
            "paused": False,
            "added_time": 1700000000,
            "spritzle.tags": ["linux", "distro"],
        },
        {
            "name": "deluge-torrent-bundle.zip",
            "info_hash": "b" * 40,
            "state": "seeding",
            "progress": 1.0,
            "download_rate": 0,
            "upload_rate": 512000,
            "total_wanted": 500000000,
            "total_size": 500000000,
            "total_done": 500000000,
            "all_time_upload": 1500000000,
            "all_time_download": 500000000,
            "num_peers": 8,
            "num_seeds": 0,
            "paused": False,
            "added_time": 1700000100,
            "spritzle.tags": ["client"],
        },
        {
            "name": "paused_download.tar",
            "info_hash": "c" * 40,
            "state": "downloading",
            "progress": 0.10,
            "download_rate": 0,
            "upload_rate": 0,
            "total_wanted": 200000000,
            "total_size": 200000000,
            "total_done": 20000000,
            "all_time_upload": 0,
            "all_time_download": 20000000,
            "num_peers": 0,
            "num_seeds": 0,
            "paused": True,
            "added_time": 1700000200,
        },
        {
            "name": "errored_torrent.dat",
            "info_hash": "d" * 40,
            "state": "downloading",
            "progress": 0.05,
            "download_rate": 0,
            "upload_rate": 0,
            "total_wanted": 100000000,
            "total_size": 100000000,
            "total_done": 5000000,
            "all_time_upload": 0,
            "all_time_download": 5000000,
            "num_peers": 0,
            "num_seeds": 0,
            "paused": False,
            "errc": 1,
            "last_error": "No space left on device",
            "added_time": 1700000300,
        },
    ]


def test_dashboard_state_filtering_tabs(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents

    # Tab: All
    state.filter_tab = FilterTab.ALL
    assert len(state.get_filtered_items()) == 4

    # Tab: Downloading
    state.filter_tab = FilterTab.DOWNLOADING
    dl_items = state.get_filtered_items()
    assert len(dl_items) == 1
    assert dl_items[0]["name"].startswith("archlinux")

    # Tab: Seeding
    state.filter_tab = FilterTab.SEEDING
    seed_items = state.get_filtered_items()
    assert len(seed_items) == 1
    assert seed_items[0]["name"].startswith("deluge")

    # Tab: Paused
    state.filter_tab = FilterTab.PAUSED
    paused_items = state.get_filtered_items()
    assert len(paused_items) == 1
    assert paused_items[0]["name"] == "paused_download.tar"

    # Tab: Active
    state.filter_tab = FilterTab.ACTIVE
    active_items = state.get_filtered_items()
    assert len(active_items) == 2  # archlinux and deluge

    # Tab: Error
    state.filter_tab = FilterTab.ERROR
    err_items = state.get_filtered_items()
    assert len(err_items) == 1
    assert err_items[0]["name"] == "errored_torrent.dat"


def test_dashboard_state_cycle_filter_tab(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents
    assert state.filter_tab == FilterTab.ALL

    state.cycle_filter_tab(forward=True)
    assert state.filter_tab == FilterTab.DOWNLOADING

    state.cycle_filter_tab(forward=True)
    assert state.filter_tab == FilterTab.SEEDING

    state.cycle_filter_tab(forward=False)
    assert state.filter_tab == FilterTab.DOWNLOADING


def test_dashboard_state_search_query(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents

    state.search_query = "arch"
    items = state.get_filtered_items()
    assert len(items) == 1
    assert items[0]["name"].startswith("archlinux")

    state.search_query = "distro"  # tag matching
    items = state.get_filtered_items()
    assert len(items) == 1
    assert items[0]["name"].startswith("archlinux")

    state.search_query = "nonexistent"
    assert len(state.get_filtered_items()) == 0


def test_dashboard_state_sorting(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents

    # Sort by download_rate (descending)
    state.sort_column = "download_rate"
    state.sort_ascending = False
    items = state.get_filtered_items()
    assert items[0]["download_rate"] == 2048000

    # Sort by upload_rate (descending)
    state.sort_column = "upload_rate"
    state.sort_ascending = False
    items = state.get_filtered_items()
    assert items[0]["upload_rate"] == 512000

    # Sort by name (A-Z)
    state.sort_column = "name"
    state.sort_ascending = False  # For name, sort_ascending=False produces A-Z
    items = state.get_filtered_items()
    assert items[0]["name"].startswith("archlinux")

    # Toggle ascending / descending
    state.sort_ascending = True
    items = state.get_filtered_items()
    assert items[-1]["name"].startswith("archlinux")


def test_dashboard_state_selection_and_multi_select(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents
    items = state.get_filtered_items()

    assert state.selected_index == 0
    selected = state.get_selected_torrent(items)
    assert selected is not None
    assert selected["name"].startswith("archlinux")

    # Move cursor down
    state.move_selection(1, len(items))
    sel2 = state.get_selected_torrent(items)
    assert sel2 is not None
    assert sel2["name"].startswith("deluge")

    # Multi-selection toggle
    assert len(state.selected_hashes) == 0
    state.toggle_select_current(items)
    assert len(state.selected_hashes) == 1
    assert "b" * 40 in state.selected_hashes

    # Targets when multi-selection active
    targets = state.get_target_hashes(items)
    assert targets == ["b" * 40]

    # Select all toggle
    state.toggle_select_all(items)
    assert len(state.selected_hashes) == 4
    state.toggle_select_all(items)
    assert len(state.selected_hashes) == 0


def test_dashboard_state_column_toggle():
    state = DashboardState()
    assert "eta" in state.visible_columns

    state.toggle_column("eta")
    assert "eta" not in state.visible_columns

    state.toggle_column("eta")
    assert "eta" in state.visible_columns

    # Add optional column
    assert "tags" not in state.visible_columns
    state.toggle_column("tags")
    assert "tags" in state.visible_columns


def test_handle_key_input_navigation(sample_torrents):
    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        quit_event = asyncio.Event()
        bg_tasks = set()
        client = MagicMock()

        # Move down with 'j'
        await handle_key_input("j", client, state, quit_event, bg_tasks)
        assert state.selected_index == 1

        # Move down with 'down'
        await handle_key_input("down", client, state, quit_event, bg_tasks)
        assert state.selected_index == 2

        # Move up with 'k'
        await handle_key_input("k", client, state, quit_event, bg_tasks)
        assert state.selected_index == 1

        # Jump to bottom with 'G'
        await handle_key_input("G", client, state, quit_event, bg_tasks)
        assert state.selected_index == len(sample_torrents) - 1

        # Jump to top with 'g'
        await handle_key_input("g", client, state, quit_event, bg_tasks)
        assert state.selected_index == 0

    asyncio.run(_test())


def test_handle_key_input_filter_tabs(sample_torrents):
    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        quit_event = asyncio.Event()
        bg_tasks = set()
        client = MagicMock()

        # Press '2' for downloading
        await handle_key_input("2", client, state, quit_event, bg_tasks)
        assert state.filter_tab == FilterTab.DOWNLOADING
        assert len(state.get_filtered_items()) == 1

        # Press '3' for seeding
        await handle_key_input("3", client, state, quit_event, bg_tasks)
        assert state.filter_tab == FilterTab.SEEDING
        assert len(state.get_filtered_items()) == 1

        # Press '1' for all
        await handle_key_input("1", client, state, quit_event, bg_tasks)
        assert state.filter_tab == FilterTab.ALL
        assert len(state.get_filtered_items()) == 4

    asyncio.run(_test())


def test_handle_key_input_inspector_and_modals(sample_torrents):
    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        quit_event = asyncio.Event()
        bg_tasks = set()
        client = MagicMock()

        # Press Enter or 'i' to enter inspector view
        await handle_key_input("enter", client, state, quit_event, bg_tasks)
        assert state.view_mode == "inspector"
        assert state.inspector_tab == "summary"

        # Switch inspector tabs
        await handle_key_input("2", client, state, quit_event, bg_tasks)
        assert state.inspector_tab == "files"

        await handle_key_input("tab", client, state, quit_event, bg_tasks)
        assert state.inspector_tab == "trackers"

        # Exit inspector with Escape
        await handle_key_input("escape", client, state, quit_event, bg_tasks)
        assert state.view_mode == "list"

        # Open help with '?'
        await handle_key_input("?", client, state, quit_event, bg_tasks)
        assert state.view_mode == "help"

        await handle_key_input("escape", client, state, quit_event, bg_tasks)
        assert state.view_mode == "list"

        # Open column selector with 'c'
        await handle_key_input("c", client, state, quit_event, bg_tasks)
        assert state.view_mode == "columns"

        # Press 'c' to toggle Tags column (12th column, key 'c')
        assert "tags" not in state.visible_columns
        await handle_key_input("c", client, state, quit_event, bg_tasks)
        assert "tags" in state.visible_columns
        assert state.view_mode == "columns"  # Still in columns view!

        # Toggle 'tags' back off with 'c'
        await handle_key_input("c", client, state, quit_event, bg_tasks)
        assert "tags" not in state.visible_columns
        assert state.view_mode == "columns"

        # Navigate down and toggle with Space
        assert state.column_cursor == 0
        await handle_key_input("down", client, state, quit_event, bg_tasks)
        assert state.column_cursor == 1
        # Column 1 is 'state' (initially in visible_columns)
        assert "state" in state.visible_columns
        await handle_key_input(" ", client, state, quit_event, bg_tasks)
        assert "state" not in state.visible_columns

        # Exit with Enter
        await handle_key_input("enter", client, state, quit_event, bg_tasks)
        assert state.view_mode == "list"

    asyncio.run(_test())


def test_handle_key_input_search_mode(sample_torrents):
    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        quit_event = asyncio.Event()
        bg_tasks = set()
        client = MagicMock()

        # Enter search mode with '/'
        await handle_key_input("/", client, state, quit_event, bg_tasks)
        assert state.search_mode is True

        # Type 'd', 'e', 'l'
        await handle_key_input("d", client, state, quit_event, bg_tasks)
        await handle_key_input("e", client, state, quit_event, bg_tasks)
        await handle_key_input("l", client, state, quit_event, bg_tasks)
        assert state.search_query == "del"
        assert len(state.get_filtered_items()) == 1
        assert state.get_filtered_items()[0]["name"].startswith("deluge")

        # Press Enter to finalize search
        await handle_key_input("enter", client, state, quit_event, bg_tasks)
        assert state.search_mode is False
        assert state.search_query == "del"

        # Press Escape in list mode to clear search
        await handle_key_input("escape", client, state, quit_event, bg_tasks)
        assert state.search_query == ""
        assert len(state.get_filtered_items()) == 4

    asyncio.run(_test())


def test_handle_key_input_command_mode(sample_torrents):
    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        quit_event = asyncio.Event()
        bg_tasks = set()
        client = MagicMock()

        # Enter command mode with ':'
        await handle_key_input(":", client, state, quit_event, bg_tasks)
        assert state.command_mode is True
        assert state.command_buffer == ""

        # Type "help"
        for char in "help":
            await handle_key_input(char, client, state, quit_event, bg_tasks)
        assert state.command_buffer == "help"

        # Submit with Enter
        await handle_key_input("enter", client, state, quit_event, bg_tasks)
        assert state.command_mode is False
        await asyncio.sleep(0.01)
        assert state.view_mode == "help"

    asyncio.run(_test())


def test_execute_command_filtering_and_sorting(sample_torrents):
    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        quit_event = asyncio.Event()
        client = MagicMock()

        # :sort name asc
        await execute_command(":sort name asc", client, state, quit_event)
        assert state.sort_column == "name"
        assert state.sort_ascending is True

        # :sort download_rate desc
        await execute_command(":sort download_rate desc", client, state, quit_event)
        assert state.sort_column == "download_rate"
        assert state.sort_ascending is False

        # :filter state=seeding
        await execute_command(":filter state=seeding", client, state, quit_event)
        assert state.custom_query == "state=seeding"
        assert len(state.get_filtered_items()) == 1

        # :clear
        await execute_command(":clear", client, state, quit_event)
        assert state.custom_query is None
        assert state.search_query == ""
        assert len(state.get_filtered_items()) == 4

        # :col +tags
        await execute_command(":col +tags", client, state, quit_event)
        assert "tags" in state.visible_columns

        # :col -tags
        await execute_command(":col -tags", client, state, quit_event)
        assert "tags" not in state.visible_columns

        # :quit
        assert not quit_event.is_set()
        await execute_command(":q", client, state, quit_event)
        assert quit_event.is_set()

    asyncio.run(_test())


def test_execute_command_actions(sample_torrents):
    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        quit_event = asyncio.Event()

        client = MagicMock()
        client.url = lambda path: f"http://localhost:8080/{path}"
        post_mock = AsyncMock()
        client.session.post.return_value.__aenter__.return_value = post_mock
        post_mock.status = 200

        with patch("spritzle.cli.dashboard._batch_action") as mock_batch:
            mock_batch.return_value = None
            # :pause
            await execute_command(":pause", client, state, quit_event)
            mock_batch.assert_called_once()
            assert "Paused 1" in str(state.status_message)

        with patch("spritzle.cli.dashboard._batch_action") as mock_batch:
            mock_batch.return_value = None
            # :resume all
            await execute_command(":resume all", client, state, quit_event)
            mock_batch.assert_called_once()
            assert "Resumed all (4)" in str(state.status_message)

    asyncio.run(_test())


def test_build_dashboard_renderable_with_state(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents
    c = Console(width=130, height=30)

    # 1. Main List Table
    panel = build_dashboard_renderable(
        state.get_filtered_items(),
        {"dht.dht_nodes": 42, "peer.num_peers_connected": 20},
        is_color=True,
        height=30,
        state=state,
    )
    assert panel.height == 30
    with c.capture() as cap:
        c.print(panel)
    output = cap.get()
    assert "Spritzle Torrent Monitor" in output
    assert "archlinux" in output
    assert "[1:All]" in output

    # 1b. Test selection indicator with Space
    state.selected_hashes.add("a" * 40)
    panel_sel = build_dashboard_renderable(
        state.get_filtered_items(),
        {"dht.dht_nodes": 42, "peer.num_peers_connected": 20},
        is_color=True,
        height=30,
        state=state,
    )
    with c.capture() as cap:
        c.print(panel_sel)
    output_sel = cap.get()
    assert "[x]" in output_sel
    assert "[ ]" in output_sel
    assert "Selected: 1" in strip_ansi(output_sel)
    assert "1 selected" in strip_ansi(output_sel)
    state.selected_hashes.clear()

    # 2. Inspector View
    state.view_mode = "inspector"
    state.inspector_data = sample_torrents[0]
    panel_ins = build_dashboard_renderable(
        state.get_filtered_items(),
        {},
        is_color=True,
        height=30,
        state=state,
    )
    with c.capture() as cap:
        c.print(panel_ins)
    output_ins = cap.get()
    assert "Torrent Inspector" in output_ins
    assert "archlinux" in output_ins

    # 3. Help View
    state.view_mode = "help"
    panel_help = build_dashboard_renderable([], {}, is_color=True, height=30, state=state)
    with c.capture() as cap:
        c.print(panel_help)
    output_help = cap.get()
    assert "Interactive Dashboard Help" in output_help

    # 4. Columns View
    state.view_mode = "columns"
    panel_cols = build_dashboard_renderable([], {}, is_color=True, height=30, state=state)
    with c.capture() as cap:
        c.print(panel_cols)
    output_cols = cap.get()
    assert "Customize Visible Columns" in output_cols


def test_dashboard_cursor_active_passive_behavior(sample_torrents):
    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        c = Console(width=130, height=30)
        client = MagicMock()
        quit_event = asyncio.Event()
        bg_tasks = set()

        # 1. Initially cursor is inactive (passive mode)
        assert state.cursor_active is False
        panel = build_dashboard_renderable(
            state.get_filtered_items(),
            {},
            is_color=True,
            height=30,
            state=state,
        )
        with c.capture() as cap:
            c.print(panel)
        output = cap.get()
        assert "▸" not in output
        assert ">" not in output

        # Pressing 'p' when cursor is inactive and nothing is checked should NOT pause anything
        await handle_key_input("p", client, state, quit_event, bg_tasks)
        assert state.status_message == "No torrent selected"
        assert state.status_is_error is True

        # 2. Moving down activates the cursor
        await handle_key_input("down", client, state, quit_event, bg_tasks)
        assert state.cursor_active is True
        assert state.selected_index == 1

        # Renders subtle pointer ▸
        panel_active = build_dashboard_renderable(
            state.get_filtered_items(),
            {},
            is_color=True,
            height=30,
            state=state,
        )
        with c.capture() as cap:
            c.print(panel_active)
        output_active = cap.get()
        assert "▸" in output_active

        # 3. Pressing escape deactivates the cursor back to passive mode
        await handle_key_input("escape", client, state, quit_event, bg_tasks)
        assert state.cursor_active is False

        # Once again, pointer is gone
        panel_deactivated = build_dashboard_renderable(
            state.get_filtered_items(),
            {},
            is_color=True,
            height=30,
            state=state,
        )
        with c.capture() as cap:
            c.print(panel_deactivated)
        output_deactivated = cap.get()
        assert "▸" not in output_deactivated

    asyncio.run(_test())


def test_dashboard_interactive_submodes_and_keys(sample_torrents):
    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        client = MagicMock()
        quit_event = asyncio.Event()
        bg_tasks = set()

        # 1. Command Mode navigation and editing
        state.command_mode = True
        state.command_buffer = "pause"
        state.command_cursor = 5
        state.command_history = ["list", "resume"]

        await handle_key_input("left", client, state, quit_event, bg_tasks)
        assert state.command_cursor == 4
        await handle_key_input("right", client, state, quit_event, bg_tasks)
        assert state.command_cursor == 5
        await handle_key_input("home", client, state, quit_event, bg_tasks)
        assert state.command_cursor == 0
        await handle_key_input("end", client, state, quit_event, bg_tasks)
        assert state.command_cursor == 5
        await handle_key_input("delete", client, state, quit_event, bg_tasks)
        assert state.command_buffer == "pause"
        await handle_key_input("home", client, state, quit_event, bg_tasks)
        await handle_key_input("delete", client, state, quit_event, bg_tasks)
        assert state.command_buffer == "ause"
        await handle_key_input("up", client, state, quit_event, bg_tasks)
        assert state.command_buffer == "resume"
        await handle_key_input("down", client, state, quit_event, bg_tasks)
        assert state.command_buffer == ""
        await handle_key_input("escape", client, state, quit_event, bg_tasks)
        assert state.command_mode is False

        # 2. Search Mode editing and cancel
        state.search_mode = True
        state.search_buffer = "arch"
        await handle_key_input("backspace", client, state, quit_event, bg_tasks)
        assert state.search_buffer == "arc"
        await handle_key_input("x", client, state, quit_event, bg_tasks)
        assert state.search_buffer == "arcx"
        await handle_key_input("escape", client, state, quit_event, bg_tasks)
        assert state.search_mode is False
        assert state.search_buffer == ""

        # 3. Columns View navigation & toggle
        state.view_mode = "columns"
        state.column_cursor = 1
        await handle_key_input("down", client, state, quit_event, bg_tasks)
        assert state.column_cursor == 2
        await handle_key_input("j", client, state, quit_event, bg_tasks)
        assert state.column_cursor == 3
        await handle_key_input("up", client, state, quit_event, bg_tasks)
        assert state.column_cursor == 2
        await handle_key_input("k", client, state, quit_event, bg_tasks)
        assert state.column_cursor == 1
        await handle_key_input("escape", client, state, quit_event, bg_tasks)
        assert state.view_mode == "list"

        # 4. Confirmation Prompt Mode
        called = False
        async def on_confirm():
            nonlocal called
            called = True

        state.confirm_prompt = "Delete torrent?"
        state.confirm_delete_callback = on_confirm
        await handle_key_input("d", client, state, quit_event, bg_tasks)
        assert state.confirm_prompt is None
        await asyncio.sleep(0.01)
        assert called is True

        # Cancel confirmation
        state.confirm_prompt = "Cancel?"
        await handle_key_input("n", client, state, quit_event, bg_tasks)
        assert state.confirm_prompt is None
        assert state.status_message == "Action cancelled"

        # 5. Inspector with full sub-details
        state.view_mode = "inspector"
        state.inspector_data = sample_torrents[0]
        state.inspector_files = [{"index": 0, "path": "file1.iso", "size": 1024, "progress": 1.0, "priority": 4}]
        state.inspector_peers = [{"ip": "1.2.3.4:5678", "client": "Deluge", "down_speed": 500000, "up_speed": 100000, "progress": 0.8}]
        state.inspector_trackers = [{"tier": 0, "url": "http://tracker.example.com", "updating": False, "fails": 0}]
        panel = build_dashboard_renderable(sample_torrents, {}, is_color=True, height=40, state=state)
        assert panel is not None

        panel_plain = build_dashboard_renderable(sample_torrents, {}, is_color=False, height=40, state=state)
        assert panel_plain is not None

    asyncio.run(_test())


def test_dashboard_execute_command_full(sample_torrents):
    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        client = MagicMock()
        client.url = lambda path: f"http://localhost/{path}"
        client.session = MagicMock()
        quit_event = asyncio.Event()

        # Quit
        await execute_command(":q", client, state, quit_event)
        assert quit_event.is_set()

        # Empty command
        await execute_command("   ", client, state, quit_event)

        # Pause all
        await execute_command(":pause all", client, state, quit_event)
        assert "Paused all" in (state.status_message or "")

        # Resume all
        await execute_command(":resume all", client, state, quit_event)
        assert "Resumed all" in (state.status_message or "")

        # Pause and resume selected
        state.selected_hashes.add("a" * 40)
        await execute_command(":pause", client, state, quit_event)
        assert "Paused 1" in (state.status_message or "")

        state.selected_hashes.add("a" * 40)
        await execute_command(":resume", client, state, quit_event)
        assert "Resumed 1" in (state.status_message or "")

        # Reannounce
        state.selected_hashes.add("a" * 40)
        await execute_command(":reannounce", client, state, quit_event)
        assert "Reannounced 1" in (state.status_message or "")

        # Delete with --delete-files
        state.selected_hashes.add("a" * 40)
        await execute_command(":rm --delete-files", client, state, quit_event)
        assert "Removed 1" in (state.status_message or "")

        # Delete prompt
        state.selected_hashes.add("b" * 40)
        await execute_command(":rm", client, state, quit_event)
        assert state.confirm_prompt is not None
        assert state.confirm_callback is not None

        # Add command without args
        await execute_command(":add", client, state, quit_event)
        assert state.status_is_error is True
        assert "Usage" in (state.status_message or "")

        # Add command with invalid file
        await execute_command(":add /nonexistent/file.torrent", client, state, quit_event)
        assert state.status_is_error is True
        assert "File not found" in (state.status_message or "")

        # Filter command
        await execute_command(":filter state.eq=downloading", client, state, quit_event)
        assert state.custom_query == "state.eq=downloading"
        await execute_command(":filter clear", client, state, quit_event)
        assert state.custom_query is None

        # Search command
        await execute_command(":search arch", client, state, quit_event)
        assert state.search_query == "arch"
        await execute_command(":search clear", client, state, quit_event)
        assert state.search_query == ""

        # Clear command
        state.search_query = "something"
        state.custom_query = "something"
        await execute_command(":clear", client, state, quit_event)
        assert state.search_query == ""
        assert state.custom_query is None

        # Sort command
        await execute_command(":sort", client, state, quit_event)
        assert "Available columns" in (state.status_message or "")

        await execute_command(":sort progress asc", client, state, quit_event)
        assert state.sort_column == "progress"
        assert state.sort_ascending is True

        await execute_command(":sort invalid_column", client, state, quit_event)
        assert state.status_is_error is True
        assert "Unknown column" in (state.status_message or "")

        # Col command
        await execute_command(":col", client, state, quit_event)
        assert state.view_mode == "columns"

        await execute_command(":col +eta", client, state, quit_event)
        assert "eta" in state.visible_columns

        await execute_command(":col -eta", client, state, quit_event)
        assert "eta" not in state.visible_columns

        await execute_command(":col reset", client, state, quit_event)
        assert "reset" in (state.status_message or "")

        await execute_command(":col invalid", client, state, quit_event)
        assert state.status_is_error is True

        # Move command
        await execute_command(":move", client, state, quit_event)
        assert state.status_is_error is True

        # Help command
        await execute_command(":help", client, state, quit_event)
        assert state.view_mode == "help"

        # Unknown command
        await execute_command(":unknown_cmd", client, state, quit_event)
        assert state.status_is_error is True

    asyncio.run(_test())


def test_dashboard_sort_keys(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents

    columns_to_test = [
        "name", "state", "progress", "size", "done",
        "download_rate", "upload_rate", "peers", "seeds",
        "eta", "ratio", "added"
    ]
    for col in columns_to_test:
        state.sort_column = col
        state.sort_ascending = True
        items_asc = state.get_filtered_items()
        assert len(items_asc) == len(sample_torrents)

        state.sort_ascending = False
        items_desc = state.get_filtered_items()
        assert len(items_desc) == len(sample_torrents)


def test_dashboard_fetch_and_run_functions(sample_torrents):
    from spritzle.cli.dashboard import (
        fetch_torrent_data,
        fetch_torrent_detail,
        fetch_torrent_files,
        fetch_torrent_trackers,
        fetch_torrent_peers,
        fetch_session_stats,
        fetch_torrents_with_status,
        render_single_watch_panel,
        watch_single_torrent,
        run_dashboard,
        _sleep_or_quit,
        _build_filter_bar_text,
        _build_help_panel,
        _build_columns_panel,
        _build_footer_status,
    )

    async def _test():
        # Setup mock client
        client = MagicMock()
        client.url = lambda path: f"http://localhost/{path}"

        # Context manager for responses
        class MockResp:
            def __init__(self, data, status=200):
                self._data = data
                self.status = status
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def json(self):
                return self._data
            async def text(self):
                return str(self._data)

        # Mock GET endpoints
        def mock_get(url, **kwargs):
            if "torrent/" in url and "/files" in url:
                return MockResp([{"index": 0, "path": "file1.iso"}])
            elif "torrent/" in url and "/trackers" in url:
                return MockResp([{"tier": 0, "url": "http://tracker.com"}])
            elif "torrent/" in url and "/peers" in url:
                return MockResp([{"ip": "1.2.3.4"}])
            elif "detail=full" in url:
                return MockResp(dict(sample_torrents[0]))
            elif "session/stats" in url:
                return MockResp({"dht.dht_nodes": 50, "peer.num_peers_connected": 5})
            elif "torrent/" in url:
                return MockResp(dict(sample_torrents[0]))
            elif url.endswith("/torrent") or url.endswith("torrent"):
                return MockResp([dict(sample_torrents[0])])
            return MockResp({})

        client.session.get = MagicMock(side_effect=mock_get)

        # Test fetch functions
        data = await fetch_torrent_data(client, "a" * 40)
        assert data is not None
        detail = await fetch_torrent_detail(client, "a" * 40)
        assert detail is not None
        files = await fetch_torrent_files(client, "a" * 40)
        assert len(files) == 1
        trackers = await fetch_torrent_trackers(client, "a" * 40)
        assert len(trackers) == 1
        peers = await fetch_torrent_peers(client, "a" * 40)
        assert len(peers) == 1
        stats = await fetch_session_stats(client)
        assert stats.get("dht.dht_nodes") == 50
        torrents = await fetch_torrents_with_status(client, query=["state=downloading"])
        assert len(torrents) == 1

        # Test render_single_watch_panel
        panel_color = render_single_watch_panel(sample_torrents[0], is_color=True)
        assert panel_color is not None
        panel_plain = render_single_watch_panel(sample_torrents[0], is_color=False)
        assert panel_plain is not None

        # Test watch_single_torrent once
        await watch_single_torrent(client, "a" * 40, once=True, color_opt=False)
        await watch_single_torrent(client, "a" * 40, once=True, color_opt=True)

        # Test _sleep_or_quit
        quit_ev = asyncio.Event()
        assert await _sleep_or_quit(0.01, None) is False
        assert await _sleep_or_quit(0.01, quit_ev) is False
        quit_ev.set()
        assert await _sleep_or_quit(0.01, quit_ev) is True

        # Test plain builder functions
        state = DashboardState()
        state.raw_torrents = sample_torrents
        assert _build_filter_bar_text(state, is_color=False) is not None
        assert _build_help_panel(is_color=False) is not None
        assert _build_columns_panel(state, is_color=False) is not None
        assert _build_footer_status(state, is_color=False) is not None

        # Test run_dashboard once
        await run_dashboard(client, once=True, plain=True)
        await run_dashboard(client, once=True, plain=False, color_opt=True, fullscreen=False)

    asyncio.run(_test())


def test_dashboard_inspector_tabs(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents
    state.cursor_active = True
    state.selected_index = 0
    state.view_mode = "inspector"
    state.inspector_data = dict(sample_torrents[0])
    state.inspector_data["last_error"] = "Tracker down"

    # 0. Inspector summary tab (color and non-color)
    state.inspector_tab = "summary"
    render_summary_color = build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True)
    assert render_summary_color is not None
    render_summary_plain = build_dashboard_renderable(sample_torrents, {}, state=state, is_color=False)
    assert render_summary_plain is not None

    # 1. Inspector files tab (empty and populated)
    state.inspector_tab = "files"
    state.inspector_files = []
    render_empty_files = build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True)
    assert render_empty_files is not None

    state.inspector_files = [
        {"path": "file1.iso", "size": 1000000, "progress": 0.5, "priority": 1},
        {"path": "file2.nfo", "size": 1000, "progress": 1.0, "priority": 0},
    ]
    render_files = build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True)
    assert render_files is not None

    # 2. Inspector trackers tab (empty and populated)
    state.inspector_tab = "trackers"
    state.inspector_trackers = []
    render_empty_tr = build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True)
    assert render_empty_tr is not None

    state.inspector_trackers = [
        {"tier": 0, "url": "http://tr1.org/announce", "status": "working", "seeds": 10, "peers": 20, "next_announce": 15},
    ]
    render_tr = build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True)
    assert render_tr is not None

    # 3. Inspector peers tab (empty and populated)
    state.inspector_tab = "peers"
    state.inspector_peers = []
    render_empty_peers = build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True)
    assert render_empty_peers is not None

    state.inspector_peers = [
        {"ip": "1.2.3.4:5000", "client": "Deluge 2.1.1", "download_rate": 1024, "upload_rate": 2048, "progress": 0.9, "flags": "u"},
    ]
    render_peers = build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True)
    assert render_peers is not None


def test_dashboard_key_handlers_extended(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents
    client = MagicMock()
    quit_event = asyncio.Event()
    tasks = set()

    async def _test():
        # 1. Filter tabs direct numeric keys and cycling
        await handle_key_input("5", client, state, quit_event, tasks)
        assert state.filter_tab == FilterTab.ACTIVE
        await handle_key_input("6", client, state, quit_event, tasks)
        assert state.filter_tab == FilterTab.ERROR
        await handle_key_input("7", client, state, quit_event, tasks)
        assert state.filter_tab == FilterTab.CHECKING
        await handle_key_input("tab", client, state, quit_event, tasks)
        await handle_key_input("shift_tab", client, state, quit_event, tasks)

        # 2. Sort column direct keys
        await handle_key_input("o", client, state, quit_event, tasks)
        await handle_key_input("s", client, state, quit_event, tasks)
        await handle_key_input("R", client, state, quit_event, tasks)
        await handle_key_input("n", client, state, quit_event, tasks)
        assert state.sort_column == "name"
        await handle_key_input("P", client, state, quit_event, tasks)
        assert state.sort_column == "progress"
        await handle_key_input("D", client, state, quit_event, tasks)
        assert state.sort_column == "download_rate"
        await handle_key_input("U", client, state, quit_event, tasks)
        assert state.sort_column == "upload_rate"
        await handle_key_input("Z", client, state, quit_event, tasks)
        assert state.sort_column == "size"
        await handle_key_input("E", client, state, quit_event, tasks)
        assert state.sort_column == "eta"

        # 3. Actions without targets
        state.cursor_active = False
        state.selected_hashes.clear()
        for k in ("p", "r", "d", "a"):
            await handle_key_input(k, client, state, quit_event, tasks)
            assert state.status_is_error is True
            assert "No torrent selected" in (state.status_message or "")

        # 4. Actions with target selected
        state.filter_tab = FilterTab.ALL
        state.cursor_active = True
        state.selected_index = 0
        state.selected_hashes = {sample_torrents[0]["info_hash"]}

        # Action: pause (p)
        await handle_key_input("p", client, state, quit_event, tasks)
        if tasks:
            await asyncio.gather(*tasks)
            tasks.clear()

        # Action: resume (r)
        await handle_key_input("r", client, state, quit_event, tasks)
        if tasks:
            await asyncio.gather(*tasks)
            tasks.clear()

        # Action: reannounce (a)
        await handle_key_input("a", client, state, quit_event, tasks)
        if tasks:
            await asyncio.gather(*tasks)
            tasks.clear()

        # Action: delete prompt (d)
        await handle_key_input("d", client, state, quit_event, tasks)
        assert state.confirm_prompt is not None
        assert state.confirm_callback is not None
        assert state.confirm_delete_callback is not None
        await state.confirm_callback()
        await state.confirm_delete_callback()

    asyncio.run(_test())


def test_parse_keys_from_bytes_utf8():
    assert parse_keys_from_bytes("é".encode("utf-8")) == ["é"]
    assert parse_keys_from_bytes("€".encode("utf-8")) == ["€"]
    assert parse_keys_from_bytes("🚀".encode("utf-8")) == ["🚀"]
    # Single invalid byte leading to UnicodeDecodeError
    assert parse_keys_from_bytes(b"\xc3\x28") == []


def test_dashboard_render_none_state(sample_torrents):
    p1 = build_dashboard_renderable(sample_torrents, {}, is_color=True, state=None)
    assert p1 is not None
    p2 = build_dashboard_renderable(sample_torrents, {}, is_color=False, state=None)
    assert p2 is not None
    p3 = build_dashboard_renderable([], {}, is_color=True, state=None)
    assert p3 is not None
    p4 = build_dashboard_renderable([], {}, is_color=False, state=None)
    assert p4 is not None


def test_render_single_watch_panel(sample_torrents):
    t = dict(sample_torrents[0])
    p1 = render_single_watch_panel(t, is_color=True)
    assert p1 is not None
    p2 = render_single_watch_panel(t, is_color=False)
    assert p2 is not None

    t["download_rate"] = 0
    t["total_wanted"] = 100
    t["total_done"] = 100
    p3 = render_single_watch_panel(t, is_color=True)
    assert p3 is not None


def test_confirm_mode_keys():
    async def _test():
        state = DashboardState()
        client = MagicMock()
        quit_event = asyncio.Event()
        tasks = set()

        # 1. Confirm 'y'
        cb = AsyncMock()
        state.confirm_prompt = "Confirm?"
        state.confirm_callback = cb
        await handle_key_input("y", client, state, quit_event, tasks)
        assert state.confirm_prompt is None
        if tasks:
            await asyncio.gather(*tasks)
            tasks.clear()
        cb.assert_awaited_once()

        # 2. Confirm 'd'
        cb_del = AsyncMock()
        state.confirm_prompt = "Confirm?"
        state.confirm_delete_callback = cb_del
        await handle_key_input("d", client, state, quit_event, tasks)
        assert state.confirm_prompt is None
        if tasks:
            await asyncio.gather(*tasks)
            tasks.clear()
        cb_del.assert_awaited_once()

        # 3. Confirm 'n'
        state.confirm_prompt = "Confirm?"
        await handle_key_input("n", client, state, quit_event, tasks)
        assert state.confirm_prompt is None
        assert state.status_message == "Action cancelled"

    asyncio.run(_test())


def test_fetch_helpers():
    class DummyContext:
        def __init__(self, resp):
            self.resp = resp

        async def __aenter__(self):
            return self.resp

        async def __aexit__(self, *args):
            pass

    class DummyResp:
        def __init__(self, status, json_data):
            self.status = status
            self._json = json_data

        async def json(self):
            if isinstance(self._json, Exception):
                raise self._json
            return self._json

    client = MagicMock()
    client.url = lambda p: f"http://test/{p}"

    async def _test():
        # fetch_torrent_data
        client.session.get = MagicMock(return_value=DummyContext(DummyResp(200, {"name": "test"})))
        assert (await fetch_torrent_data(client, "hash1")) == {"name": "test"}
        client.session.get = MagicMock(return_value=DummyContext(DummyResp(404, {})))
        assert (await fetch_torrent_data(client, "hash1")) is None
        client.session.get = MagicMock(side_effect=Exception("network error"))
        assert (await fetch_torrent_data(client, "hash1")) is None

        # fetch_torrent_detail
        client.session.get = MagicMock(return_value=DummyContext(DummyResp(200, {"name": "test"})))
        assert (await fetch_torrent_detail(client, "hash1")) == {"name": "test"}
        client.session.get = MagicMock(side_effect=Exception("error"))
        assert (await fetch_torrent_detail(client, "hash1")) == {}

        # fetch_torrent_files
        client.session.get = MagicMock(return_value=DummyContext(DummyResp(200, [{"path": "a"}])))
        assert (await fetch_torrent_files(client, "hash1")) == [{"path": "a"}]
        client.session.get = MagicMock(side_effect=Exception("error"))
        assert (await fetch_torrent_files(client, "hash1")) == []

        # fetch_torrent_trackers
        client.session.get = MagicMock(return_value=DummyContext(DummyResp(200, [{"url": "http://trk"}])))
        assert (await fetch_torrent_trackers(client, "hash1")) == [{"url": "http://trk"}]
        client.session.get = MagicMock(side_effect=Exception("error"))
        assert (await fetch_torrent_trackers(client, "hash1")) == []

        # fetch_torrent_peers
        client.session.get = MagicMock(return_value=DummyContext(DummyResp(200, [{"ip": "1.2.3.4"}])))
        assert (await fetch_torrent_peers(client, "hash1")) == [{"ip": "1.2.3.4"}]
        client.session.get = MagicMock(side_effect=Exception("error"))
        assert (await fetch_torrent_peers(client, "hash1")) == []

        # fetch_session_stats
        client.session.get = MagicMock(return_value=DummyContext(DummyResp(200, {"num_peers": 5})))
        assert (await fetch_session_stats(client)) == {"num_peers": 5}
        client.session.get = MagicMock(side_effect=Exception("error"))
        assert (await fetch_session_stats(client)) == {}

        # fetch_torrents_with_status (keys path)
        client.session.get = MagicMock(return_value=DummyContext(DummyResp(200, [{"info_hash": "a"}])) )
        res = await fetch_torrents_with_status(client, query=["name=test"])
        assert res == [{"info_hash": "a"}]

        # fetch_torrents_with_status (keys empty list)
        client.session.get = MagicMock(return_value=DummyContext(DummyResp(200, [])))
        res_empty = await fetch_torrents_with_status(client)
        assert res_empty == []

        # fetch_torrents_with_status (fallback to list of info_hashes)
        call_count = 0
        def get_mock(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return DummyContext(DummyResp(200, ["hash1"]))  # keys query returns list of strings
            elif call_count == 2:
                return DummyContext(DummyResp(200, ["hash1"]))  # legacy query returns list of strings
            else:
                return DummyContext(DummyResp(200, {"info_hash": "hash1", "name": "found"}))
        client.session.get = MagicMock(side_effect=get_mock)
        res_fallback = await fetch_torrents_with_status(client)
        assert len(res_fallback) == 1
        assert res_fallback[0]["name"] == "found"

    asyncio.run(_test())


def test_watch_single_torrent_flow(sample_torrents):
    client = MagicMock()

    async def _test():
        # 1. Not found (interactive and non-interactive)
        with patch("spritzle.cli.dashboard.fetch_torrent_data", AsyncMock(return_value=None)):
            await watch_single_torrent(client, "dummy_hash", color_opt=True, once=True)
            await watch_single_torrent(client, "dummy_hash", color_opt=False, once=True)

        # 2. Found downloading once
        with patch("spritzle.cli.dashboard.fetch_torrent_data", AsyncMock(return_value=sample_torrents[0])):
            await watch_single_torrent(client, "dummy_hash", color_opt=True, once=True)
            await watch_single_torrent(client, "dummy_hash", color_opt=False, once=True)

        # 3. Found finished
        finished_data = dict(sample_torrents[0])
        finished_data["progress"] = 1.0
        finished_data["state"] = "seeding"
        with patch("spritzle.cli.dashboard.fetch_torrent_data", AsyncMock(return_value=finished_data)):
            await watch_single_torrent(client, "dummy_hash", color_opt=True, once=False)
            await watch_single_torrent(client, "dummy_hash", color_opt=False, once=False)

        # 4. CancelledError
        with patch("spritzle.cli.dashboard.fetch_torrent_data", AsyncMock(side_effect=asyncio.CancelledError())):
            await watch_single_torrent(client, "dummy_hash", color_opt=True, once=False)
            await watch_single_torrent(client, "dummy_hash", color_opt=False, once=False)

    asyncio.run(_test())


def test_interactive_dashboard_run(sample_torrents):
    client = MagicMock()

    async def _test():
        with patch("spritzle.cli.dashboard.fetch_torrents_with_status", AsyncMock(return_value=sample_torrents)), \
             patch("spritzle.cli.dashboard.fetch_session_stats", AsyncMock(return_value={"num_peers": 10})):
            # 1. Plain non-interactive mode with once=True
            await run_dashboard(client, query=["name=test"], once=True, color_opt=False, plain=True)
            # Plain mode with empty list
            with patch("spritzle.cli.dashboard.fetch_torrents_with_status", AsyncMock(return_value=[])):
                await run_dashboard(client, once=True, color_opt=False, plain=True)

            # 2. Interactive mode with once=True
            await run_dashboard(client, once=True, color_opt=True, fullscreen=True)

            # 3. Interrupted
            with patch("spritzle.cli.dashboard.fetch_torrents_with_status", AsyncMock(side_effect=KeyboardInterrupt())):
                await run_dashboard(client, once=False, color_opt=False, plain=True)

    asyncio.run(_test())


def test_sleep_or_quit():
    async def _test():
        # 1. No quit event
        res = await _sleep_or_quit(0.01, None)
        assert res is False

        # 2. Already set quit event
        ev = asyncio.Event()
        ev.set()
        assert (await _sleep_or_quit(0.01, ev)) is True

        # 3. Short interval, not set
        ev.clear()
        assert (await _sleep_or_quit(0.01, ev)) is False

        # 4. Longer interval with quit set mid-sleep
        ev.clear()
        async def _set_after():
            await asyncio.sleep(0.02)
            ev.set()
        asyncio.create_task(_set_after())
        res = await _sleep_or_quit(0.1, ev)
        assert res is True

    asyncio.run(_test())


def test_key_press_watcher():
    async def _test():
        ev = asyncio.Event()
        q = asyncio.Queue()

        watcher = KeyPressWatcher(quit_event=ev, key_queue=q)
        # Test signal handling
        watcher._on_signal()
        assert ev.is_set()

        # Test on_stdin with simulated data
        watcher._fd = 1
        with patch("os.read", return_value=b"q"):
            watcher._on_stdin()
        assert not q.empty()
        assert q.get_nowait() == "q"

        # Test on_stdin with EOF
        loop_mock = MagicMock()
        watcher._loop = loop_mock
        with patch("os.read", return_value=b""):
            watcher._on_stdin()
        loop_mock.remove_reader.assert_called_with(1)

        # Test cleanup
        watcher._sigint_installed = True
        watcher._sigterm_installed = True
        watcher._restorer = MagicMock()
        watcher._cleanup()
        assert watcher._fd is None

    asyncio.run(_test())


def test_dashboard_rendering_modes(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents

    # 1. Search query active in filter bar
    state.search_query = "arch"
    assert build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True) is not None
    assert build_dashboard_renderable(sample_torrents, {}, state=state, is_color=False) is not None

    # 2. Custom query active in filter bar
    state.custom_query = "downloading"
    assert build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True) is not None
    assert build_dashboard_renderable(sample_torrents, {}, state=state, is_color=False) is not None

    # 3. Selected hashes active in filter bar
    state.selected_hashes = {sample_torrents[0]["info_hash"]}
    assert build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True) is not None
    assert build_dashboard_renderable(sample_torrents, {}, state=state, is_color=False) is not None

    # 4. Command mode footer
    state.command_mode = True
    state.command_buffer = "pause all"
    state.command_cursor = 5
    assert build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True) is not None
    assert build_dashboard_renderable(sample_torrents, {}, state=state, is_color=False) is not None

    # 5. Search mode footer
    state.command_mode = False
    state.search_mode = True
    state.search_buffer = "test"
    assert build_dashboard_renderable(sample_torrents, {}, state=state, is_color=True) is not None
    assert build_dashboard_renderable(sample_torrents, {}, state=state, is_color=False) is not None


def test_dashboard_commands_and_actions(sample_torrents, tmp_path):
    class DummyContext:
        def __init__(self, status=200, text="ok"):
            self.status = status
            self._text = text

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def text(self):
            return self._text

    client = MagicMock()
    client.url = lambda p: f"http://test/{p}"
    client.session.post = MagicMock(return_value=DummyContext(200, "ok"))

    async def _test():
        state = DashboardState()
        state.raw_torrents = sample_torrents
        state.selected_index = 0
        state.cursor_active = True
        quit_event = asyncio.Event()

        # 1. :pause all & :resume all
        await execute_command(":pause all", client, state, quit_event)
        assert "Paused all" in (state.status_message or "")
        await execute_command(":resume all", client, state, quit_event)
        assert "Resumed all" in (state.status_message or "")

        # 2. :sort commands
        await execute_command(":sort", client, state, quit_event)
        assert "Available columns" in (state.status_message or "")
        await execute_command(":sort progress asc", client, state, quit_event)
        assert state.sort_column == "progress"
        assert state.sort_ascending is True
        await execute_command(":sort invalid_col", client, state, quit_event)
        assert state.status_is_error is True

        # 3. :col commands
        await execute_command(":col", client, state, quit_event)
        assert state.view_mode == "columns"
        await execute_command(":col reset", client, state, quit_event)
        await execute_command(":col +seeds", client, state, quit_event)
        assert "seeds" in state.visible_columns
        await execute_command(":col -seeds", client, state, quit_event)
        assert "seeds" not in state.visible_columns
        await execute_command(":col -nonexistent", client, state, quit_event)
        assert state.status_is_error is True
        await execute_command(":col invalid", client, state, quit_event)
        assert state.status_is_error is True

        # 4. :filter & :search & :clear
        await execute_command(":filter name=test", client, state, quit_event)
        assert state.custom_query == "name=test"
        await execute_command(":filter clear", client, state, quit_event)
        assert state.custom_query is None
        await execute_command(":search arch", client, state, quit_event)
        assert state.search_query == "arch"
        await execute_command(":search clear", client, state, quit_event)
        assert state.search_query == ""
        await execute_command(":clear", client, state, quit_event)
        assert state.search_query == ""
        assert state.custom_query is None

        # 5. :move command
        await execute_command(":move", client, state, quit_event)
        assert state.status_is_error is True
        # Target selected move
        await execute_command(":move /tmp/new_path", client, state, quit_event)
        assert "Moved storage" in (state.status_message or "")

        # 6. :add command
        await execute_command(":add", client, state, quit_event)
        assert state.status_is_error is True
        # add URL
        await execute_command(":add https://example.com/test.torrent", client, state, quit_event)
        assert "Torrent added successfully" in (state.status_message or "")
        # add nonexistent file
        await execute_command(":add /tmp/does_not_exist_torrent", client, state, quit_event)
        assert "File not found" in (state.status_message or "")
        # add real file
        fake_torrent = tmp_path / "test.torrent"
        fake_torrent.write_bytes(b"dummy torrent content")
        await execute_command(f":add {fake_torrent}", client, state, quit_event)
        assert "successfully" in (state.status_message or "")

        # 7. :rm with flags
        await execute_command(":rm --delete-files", client, state, quit_event)
        assert "files deleted" in (state.status_message or "")

    asyncio.run(_test())


def test_key_press_watcher_aenter():
    async def _test():
        ev = asyncio.Event()
        q = asyncio.Queue()
        r_fd, w_fd = os.pipe()
        try:
            with patch("os.isatty", return_value=True), \
                 patch("termios.tcgetattr", return_value=[0, 0, 0, 0, 0, 0, [0] * 32]), \
                 patch("tty.setcbreak"), \
                 patch("termios.tcsetattr"):
                watcher = KeyPressWatcher(quit_event=ev, fd=r_fd, key_queue=q)
                async with watcher:
                    assert watcher._fd == r_fd
                    # Trigger restorer
                    if watcher._restorer:
                        watcher._restorer()
        finally:
            os.close(r_fd)
            os.close(w_fd)

    asyncio.run(_test())


def test_dashboard_key_handlers_modes_navigation(sample_torrents):
    state = DashboardState()
    state.raw_torrents = sample_torrents
    client = MagicMock()
    quit_event = asyncio.Event()
    tasks = set()

    async def _test():
        # 1. Command mode cursor and history navigation
        state.command_mode = True
        state.command_buffer = "hello"
        state.command_cursor = 5
        state.command_history = ["cmd1", "cmd2"]
        state.command_history_idx = -1

        await handle_key_input("backspace", client, state, quit_event, tasks)
        assert state.command_buffer == "hell"
        await handle_key_input("left", client, state, quit_event, tasks)
        assert state.command_cursor == 3
        await handle_key_input("delete", client, state, quit_event, tasks)
        assert state.command_buffer == "hel"
        await handle_key_input("home", client, state, quit_event, tasks)
        assert state.command_cursor == 0
        await handle_key_input("right", client, state, quit_event, tasks)
        assert state.command_cursor == 1
        await handle_key_input("end", client, state, quit_event, tasks)
        assert state.command_cursor == 3
        await handle_key_input("up", client, state, quit_event, tasks)
        assert state.command_buffer == "cmd2"
        await handle_key_input("up", client, state, quit_event, tasks)
        assert state.command_buffer == "cmd1"
        await handle_key_input("down", client, state, quit_event, tasks)
        assert state.command_buffer == "cmd2"
        await handle_key_input("down", client, state, quit_event, tasks)
        assert state.command_buffer == ""

        # 2. Inspector mode tab navigation
        state.command_mode = False
        state.view_mode = "inspector"
        state.inspector_tab = "summary"
        await handle_key_input("2", client, state, quit_event, tasks)
        assert state.inspector_tab == "files"
        await handle_key_input("3", client, state, quit_event, tasks)
        assert state.inspector_tab == "trackers"
        await handle_key_input("4", client, state, quit_event, tasks)
        assert state.inspector_tab == "peers"
        await handle_key_input("1", client, state, quit_event, tasks)
        assert state.inspector_tab == "summary"
        await handle_key_input("tab", client, state, quit_event, tasks)
        assert state.inspector_tab == "files"
        await handle_key_input("shift_tab", client, state, quit_event, tasks)
        assert state.inspector_tab == "summary"
        await handle_key_input("right", client, state, quit_event, tasks)
        assert state.inspector_tab == "files"
        await handle_key_input("left", client, state, quit_event, tasks)
        assert state.inspector_tab == "summary"
        await handle_key_input("escape", client, state, quit_event, tasks)
        assert state.view_mode == "list"

        # 3. List navigation page_up, page_down, star
        state.view_mode = "list"
        state.filter_tab = FilterTab.ALL
        state.cursor_active = True
        state.selected_index = 0
        await handle_key_input("page_down", client, state, quit_event, tasks)
        await handle_key_input("page_up", client, state, quit_event, tasks)
        await handle_key_input("*", client, state, quit_event, tasks)
        assert len(state.selected_hashes) > 0
        await handle_key_input("*", client, state, quit_event, tasks)
        assert len(state.selected_hashes) == 0

    asyncio.run(_test())




