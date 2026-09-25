import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from spritzle.cli.dashboard import (
    DashboardState,
    FilterTab,
    build_dashboard_renderable,
    execute_command,
    handle_key_input,
    parse_keys_from_bytes,
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
    assert "Selected: 1" in output_sel
    assert "1 selected" in output_sel
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


