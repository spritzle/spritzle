import asyncio
import atexit
import base64
import os
from pathlib import Path
import signal
import sys
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

try:
    import termios
    import tty
except ImportError:
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]

from rich import box
from rich.console import Group
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from spritzle.cli.display import (
    BRAND_ACCENT,
    BRAND_DARK,
    BRAND_PRIMARY,
    HEADER_STYLE,
    format_bytes,
    format_datetime,
    format_eta,
    format_progress,
    format_speed,
    format_state_pill,
    get_console,
    get_display_state,
    should_use_color,
)

_active_terminal_restorers: Set[Callable[[], None]] = set()


def _restore_all_terminals() -> None:
    """Safely restore terminal settings and show cursor for all active terminal watchers."""
    for restorer in list(_active_terminal_restorers):
        try:
            restorer()
        except Exception:
            pass
    _active_terminal_restorers.clear()
    try:
        if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()
    except Exception:
        pass


atexit.register(_restore_all_terminals)


def parse_keys_from_bytes(data: bytes) -> List[str]:
    """Parse byte sequence from terminal stdin into logical key names or characters."""
    keys: List[str] = []
    i = 0
    n = len(data)
    while i < n:
        # 4-byte escape sequences
        if i + 4 <= n:
            chunk4 = data[i : i + 4]
            if chunk4 == b"\x1b[5~":
                keys.append("page_up")
                i += 4
                continue
            elif chunk4 == b"\x1b[6~":
                keys.append("page_down")
                i += 4
                continue
            elif chunk4 == b"\x1b[3~":
                keys.append("delete")
                i += 4
                continue
            elif chunk4 in (b"\x1b[1~", b"\x1b[7~"):
                keys.append("home")
                i += 4
                continue
            elif chunk4 in (b"\x1b[4~", b"\x1b[8~"):
                keys.append("end")
                i += 4
                continue

        # 3-byte escape sequences
        if i + 3 <= n:
            chunk3 = data[i : i + 3]
            if chunk3 in (b"\x1b[A", b"\x1bOA"):
                keys.append("up")
                i += 3
                continue
            elif chunk3 in (b"\x1b[B", b"\x1bOB"):
                keys.append("down")
                i += 3
                continue
            elif chunk3 in (b"\x1b[C", b"\x1bOC"):
                keys.append("right")
                i += 3
                continue
            elif chunk3 in (b"\x1b[D", b"\x1bOD"):
                keys.append("left")
                i += 3
                continue
            elif chunk3 in (b"\x1b[H", b"\x1bOH"):
                keys.append("home")
                i += 3
                continue
            elif chunk3 in (b"\x1b[F", b"\x1bOF"):
                keys.append("end")
                i += 3
                continue
            elif chunk3 == b"\x1b[Z":
                keys.append("shift_tab")
                i += 3
                continue

        # 1-byte control characters or characters
        b = data[i : i + 1]
        if b == b"\x1b":
            keys.append("escape")
            i += 1
        elif b in (b"\r", b"\n"):
            keys.append("enter")
            i += 1
        elif b in (b"\x7f", b"\x08"):
            keys.append("backspace")
            i += 1
        elif b == b"\t":
            keys.append("tab")
            i += 1
        elif b == b"\x03":
            keys.append("ctrl_c")
            i += 1
        elif b == b"\x04":
            keys.append("ctrl_d")
            i += 1
        else:
            first_byte = data[i]
            if (first_byte & 0x80) == 0:
                char_len = 1
            elif (first_byte & 0xE0) == 0xC0:
                char_len = 2
            elif (first_byte & 0xF0) == 0xE0:
                char_len = 3
            elif (first_byte & 0xF8) == 0xF0:
                char_len = 4
            else:
                char_len = 1

            chunk = data[i : i + char_len]
            try:
                char = chunk.decode("utf-8")
                keys.append(char)
            except UnicodeDecodeError:
                pass
            i += max(1, char_len)

    return keys


class KeyPressWatcher:
    """Async context manager that puts stdin in cbreak mode to detect keypresses."""

    def __init__(
        self,
        quit_event: Optional[asyncio.Event] = None,
        fd: Optional[int] = None,
        key_queue: Optional[asyncio.Queue[str]] = None,
    ) -> None:
        self.quit_event = quit_event if quit_event is not None else asyncio.Event()
        self._target_fd = fd
        self._key_queue = key_queue
        self._fd: Optional[int] = None
        self._old_settings: Optional[Any] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._restorer: Optional[Callable[[], None]] = None
        self._sigint_installed: bool = False
        self._sigterm_installed: bool = False

    async def __aenter__(self) -> "KeyPressWatcher":
        if termios is None or tty is None:
            return self
        try:
            target_fd = self._target_fd
            if target_fd is None and hasattr(sys.stdin, "fileno") and sys.stdin.isatty():
                target_fd = sys.stdin.fileno()

            if target_fd is not None and os.isatty(target_fd):
                self._old_settings = termios.tcgetattr(target_fd)
                tty.setcbreak(target_fd)
                self._fd = target_fd

                saved_fd = target_fd
                saved_settings = list(self._old_settings)

                def _do_restore() -> None:
                    if termios is not None:
                        try:
                            restored = list(saved_settings)
                            restored[3] |= (termios.ECHO | termios.ICANON | termios.ISIG)
                            termios.tcsetattr(saved_fd, termios.TCSANOW, restored)
                        except Exception:
                            pass
                    try:
                        if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
                            sys.stdout.write("\x1b[?25h")
                            sys.stdout.flush()
                    except Exception:
                        pass

                self._restorer = _do_restore
                _active_terminal_restorers.add(_do_restore)

                self._loop = asyncio.get_running_loop()
                self._loop.add_reader(self._fd, self._on_stdin)

                try:
                    self._loop.add_signal_handler(signal.SIGINT, self._on_signal)
                    self._sigint_installed = True
                except (ValueError, RuntimeError, NotImplementedError):
                    self._sigint_installed = False

                try:
                    self._loop.add_signal_handler(signal.SIGTERM, self._on_signal)
                    self._sigterm_installed = True
                except (ValueError, RuntimeError, NotImplementedError):
                    self._sigterm_installed = False
        except Exception:
            self._cleanup()
        return self

    def _on_signal(self) -> None:
        self.quit_event.set()

    def _on_stdin(self) -> None:
        try:
            if self._fd is None:
                return
            data = os.read(self._fd, 1024)
        except Exception:
            data = b""
        if not data:
            if self._loop and self._fd is not None:
                try:
                    self._loop.remove_reader(self._fd)
                except Exception:
                    pass
            return

        keys = parse_keys_from_bytes(data)
        for k in keys:
            if self._key_queue is not None:
                self._key_queue.put_nowait(k)
            elif k in ("q", "Q", "ctrl_c"):
                self.quit_event.set()

        if any(k == "ctrl_c" for k in keys):
            self.quit_event.set()

    def _cleanup(self) -> None:
        if self._loop:
            if self._sigint_installed:
                try:
                    self._loop.remove_signal_handler(signal.SIGINT)
                except (ValueError, RuntimeError, NotImplementedError):
                    pass
                self._sigint_installed = False
            if self._sigterm_installed:
                try:
                    self._loop.remove_signal_handler(signal.SIGTERM)
                except (ValueError, RuntimeError, NotImplementedError):
                    pass
                self._sigterm_installed = False
            if self._fd is not None:
                try:
                    self._loop.remove_reader(self._fd)
                except Exception:
                    pass

        if self._restorer is not None:
            self._restorer()
            _active_terminal_restorers.discard(self._restorer)
            self._restorer = None

        self._fd = None
        self._old_settings = None
        self._loop = None

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._cleanup()


async def fetch_torrent_data(client, info_hash: str) -> Optional[Dict[str, Any]]:
    """Fetch status dict for a specific torrent."""
    try:
        async with client.session.get(client.url(f"torrent/{info_hash}")) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return None


async def fetch_torrent_detail(client, info_hash: str) -> Dict[str, Any]:
    """Fetch full detail dict for a specific torrent."""
    try:
        async with client.session.get(client.url(f"torrent/{info_hash}?detail=full")) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


async def fetch_torrent_files(client, info_hash: str) -> List[Dict[str, Any]]:
    """Fetch files list for a torrent."""
    try:
        async with client.session.get(client.url(f"torrent/{info_hash}/files")) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []


async def fetch_torrent_trackers(client, info_hash: str) -> List[Dict[str, Any]]:
    """Fetch trackers list for a torrent."""
    try:
        async with client.session.get(client.url(f"torrent/{info_hash}/trackers")) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []


async def fetch_torrent_peers(client, info_hash: str) -> List[Dict[str, Any]]:
    """Fetch connected peers list for a torrent."""
    try:
        async with client.session.get(client.url(f"torrent/{info_hash}/peers")) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []


async def fetch_session_stats(client) -> Dict[str, Any]:
    """Fetch session stats dict."""
    try:
        async with client.session.get(client.url("session/stats")) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


async def fetch_torrents_with_status(client, query: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """Fetch list of torrent statuses matching query."""
    params = {}
    if query:
        for q in query:
            if "=" in q:
                k, v = q.split("=", 1)
                params[k] = v
            else:
                params[q] = ""

    dash_keys = "name,info_hash,state,progress,download_rate,upload_rate,total_wanted,total_size,total_done,all_time_download,all_time_upload,num_peers,num_seeds,paused,flags,errc,last_error,added_time,completed_time,spritzle.tags"
    params_with_keys = dict(params)
    params_with_keys["keys"] = dash_keys

    try:
        async with client.session.get(client.url("torrent"), params=params_with_keys) as resp:
            if resp.status == 200:
                torrents = await resp.json()
                if isinstance(torrents, list):
                    if torrents and isinstance(torrents[0], dict):
                        return torrents
                    elif not torrents:
                        return []
    except Exception:
        pass

    try:
        async with client.session.get(client.url("torrent"), params=params) as resp:
            if resp.status != 200:
                return []
            torrents = await resp.json()
            if not isinstance(torrents, list):
                return []
    except Exception:
        return []

    items = []
    for ih in torrents:
        data = await fetch_torrent_data(client, ih)
        if data:
            items.append(data)
    return items


def render_single_watch_panel(data: Dict[str, Any], is_color: bool = True) -> Panel:
    """Build a rich Panel representation of a single torrent's progress."""
    name = data.get("name") or data.get("info_hash", "torrent")
    info_hash = data.get("info_hash", "")
    short_hash = f"{info_hash[:8]}..." if len(info_hash) >= 8 else info_hash
    state = get_display_state(data)
    progress = float(data.get("progress", 0.0))
    dl_rate = float(data.get("download_rate", 0))
    ul_rate = float(data.get("upload_rate", 0))
    total_wanted = float(data.get("total_wanted", 0) or data.get("total_size", 0))
    total_done = float(data.get("total_done", 0))
    num_peers = int(data.get("num_peers", 0))
    num_seeds = int(data.get("num_seeds", 0))

    if dl_rate > 0 and total_wanted > total_done:
        eta_sec = (total_wanted - total_done) / dl_rate
    else:
        eta_sec = None

    status_disp = format_state_pill(state, use_color=is_color, peers=num_peers)
    prog_bar = format_progress(
        progress, human=True, width=20, style="smooth" if is_color else "blocks", use_color=is_color
    )
    size_disp = (
        f"{format_bytes(total_done)} / {format_bytes(total_wanted)}"
        if total_wanted > 0
        else format_bytes(total_done)
    )
    if is_color:
        speed_disp = f"{format_speed(dl_rate, use_color=True)}   {format_speed(ul_rate, use_color=True, is_upload=True)}"
    else:
        speed_disp = f"▼ {format_speed(dl_rate)}   ▲ {format_speed(ul_rate)}"
    peers_disp = f"{num_peers} connected ({num_seeds} seeds)"
    eta_disp = format_eta(eta_sec)

    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim", no_wrap=True)
    table.add_column()

    table.add_row("Status:", status_disp)
    table.add_row("Progress:", f"{prog_bar}  [dim]({size_disp})[/dim]" if is_color else f"{prog_bar}  ({size_disp})")
    table.add_row("Speed:", speed_disp)
    table.add_row("Peers:", peers_disp)
    table.add_row("ETA:", eta_disp)

    title = f"[bold]{escape(name)}[/bold] ([{BRAND_ACCENT}]{escape(short_hash)}[/{BRAND_ACCENT}])" if is_color else f"{name} ({short_hash})"
    return Panel(
        table,
        title=title,
        subtitle="[dim]Press Ctrl+C to stop watching[/dim]",
        border_style="dim" if is_color else "none",
    )


async def watch_single_torrent(
    client,
    info_hash: str,
    interval: float = 1.0,
    color_opt: Optional[bool] = None,
    once: bool = False,
) -> None:
    """Stream live progress of a single torrent until completion or Ctrl+C."""
    is_interactive = should_use_color(color_opt)
    console = get_console(color_opt)

    try:
        if is_interactive:
            with Live(console=console, refresh_per_second=4, transient=False) as live:
                while True:
                    data = await fetch_torrent_data(client, info_hash)
                    if not data:
                        console.print(f"[red]Torrent {info_hash} not found.[/red]")
                        break

                    live.update(render_single_watch_panel(data, is_color=True))

                    progress = float(data.get("progress", 0.0))
                    state = str(data.get("state", "")).lower()
                    if progress >= 1.0 or state in ("seeding", "finished"):
                        name = data.get("name") or info_hash
                        size = format_bytes(data.get("total_size") or data.get("total_wanted") or 0)
                        live.stop()
                        console.print(f"[bold green]✔[/bold green] Download complete: [bold]{escape(name)}[/bold] ({size})")
                        break

                    if once:
                        break
                    await asyncio.sleep(interval)
        else:
            while True:
                data = await fetch_torrent_data(client, info_hash)
                if not data:
                    print(f"Torrent {info_hash} not found.")
                    break

                name = data.get("name") or info_hash
                progress = float(data.get("progress", 0.0))
                dl_rate = float(data.get("download_rate", 0))
                ul_rate = float(data.get("upload_rate", 0))
                num_peers = int(data.get("num_peers", 0))
                total_wanted = float(data.get("total_wanted", 0) or data.get("total_size", 0))
                total_done = float(data.get("total_done", 0))
                eta_sec = (total_wanted - total_done) / dl_rate if dl_rate > 0 and total_wanted > total_done else None
                eta_str = format_eta(eta_sec)

                pct = f"{progress * 100:.1f}%"
                print(f"{name}: {pct} | DL: {format_speed(dl_rate)} | UL: {format_speed(ul_rate)} | Peers: {num_peers} | ETA: {eta_str}")

                state = str(data.get("state", "")).lower()
                if progress >= 1.0 or state in ("seeding", "finished"):
                    size = format_bytes(total_wanted)
                    print(f"Download complete: {name} ({size})")
                    break

                if once:
                    break
                await asyncio.sleep(interval)
    except (asyncio.CancelledError, KeyboardInterrupt):
        if is_interactive:
            console.print("\n[dim]Watching stopped.[/dim]")
        else:
            print("\nWatching stopped.")
    finally:
        if is_interactive:
            try:
                console.show_cursor(True)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Interactive Dashboard State & Filtering
# ---------------------------------------------------------------------------

class FilterTab:
    ALL = "all"
    DOWNLOADING = "downloading"
    SEEDING = "seeding"
    PAUSED = "paused"
    ACTIVE = "active"
    ERROR = "error"
    CHECKING = "checking"


FILTER_TABS: List[Tuple[str, str, str]] = [
    (FilterTab.ALL, "All", "1"),
    (FilterTab.DOWNLOADING, "Downloading", "2"),
    (FilterTab.SEEDING, "Seeding", "3"),
    (FilterTab.PAUSED, "Paused", "4"),
    (FilterTab.ACTIVE, "Active", "5"),
    (FilterTab.ERROR, "Errors", "6"),
    (FilterTab.CHECKING, "Checking", "7"),
]

ALL_COLUMNS: List[Tuple[str, str, Optional[int], Literal["left", "right", "center"]]] = [
    ("name", "Name", 1, "left"),
    ("state", "Status", None, "left"),
    ("progress", "Progress", None, "left"),
    ("size", "Size", None, "right"),
    ("done", "Downloaded", None, "right"),
    ("download_rate", "Down Speed", None, "right"),
    ("upload_rate", "Up Speed", None, "right"),
    ("peers", "Peers", None, "right"),
    ("seeds", "Seeds", None, "right"),
    ("eta", "ETA", None, "right"),
    ("ratio", "Ratio", None, "right"),
    ("tags", "Tags", None, "left"),
]

DEFAULT_COLUMNS: List[str] = [
    "name",
    "state",
    "progress",
    "size",
    "download_rate",
    "upload_rate",
    "peers",
    "eta",
]


class DashboardState:
    """Maintains state for the interactive dashboard session."""

    def __init__(self, query: Optional[Sequence[str]] = None) -> None:
        self.raw_torrents: List[Dict[str, Any]] = []
        self.session_stats: Dict[str, Any] = {}
        self.filter_tab: str = FilterTab.ALL
        self.search_query: str = ""
        self.custom_query: Optional[str] = " ".join(query) if query else None

        self.sort_column: str = "download_rate"
        self.sort_ascending: bool = False
        self.visible_columns: List[str] = list(DEFAULT_COLUMNS)

        self.selected_index: int = 0
        self.cursor_active: bool = False
        self.selected_hashes: Set[str] = set()
        self.scroll_offset: int = 0

        self.view_mode: str = "list"  # "list", "inspector", "help", "columns"
        self.column_cursor: int = 0
        self.inspector_tab: str = "summary"  # "summary", "files", "trackers", "peers"
        self.inspector_data: Dict[str, Any] = {}
        self.inspector_files: List[Dict[str, Any]] = []
        self.inspector_trackers: List[Dict[str, Any]] = []
        self.inspector_peers: List[Dict[str, Any]] = []
        self.inspector_scroll: int = 0

        self.command_mode: bool = False
        self.command_buffer: str = ""
        self.command_cursor: int = 0
        self.command_history: List[str] = []
        self.command_history_idx: int = -1

        self.search_mode: bool = False
        self.search_buffer: str = ""

        self.confirm_prompt: Optional[str] = None
        self.confirm_callback: Optional[Callable[[], Any]] = None
        self.confirm_delete_callback: Optional[Callable[[], Any]] = None

        self.status_message: Optional[str] = None
        self.status_is_error: bool = False
        self.status_expires_at: float = 0.0

    def set_status(self, msg: str, is_error: bool = False, timeout: float = 4.0) -> None:
        self.status_message = msg
        self.status_is_error = is_error
        try:
            now = asyncio.get_running_loop().time()
        except RuntimeError:
            now = 0.0
        self.status_expires_at = now + timeout

    def check_status_expiration(self) -> None:
        if self.status_message:
            try:
                now = asyncio.get_running_loop().time()
                if now > self.status_expires_at:
                    self.status_message = None
            except RuntimeError:
                pass

    def get_filtered_items(self) -> List[Dict[str, Any]]:
        items = list(self.raw_torrents)

        # Filter by Tab
        if self.filter_tab == FilterTab.DOWNLOADING:
            items = [t for t in items if get_display_state(t) == "downloading"]
        elif self.filter_tab == FilterTab.SEEDING:
            items = [t for t in items if get_display_state(t) in ("seeding", "finished")]
        elif self.filter_tab == FilterTab.PAUSED:
            items = [t for t in items if bool(t.get("paused")) or get_display_state(t) == "paused"]
        elif self.filter_tab == FilterTab.ACTIVE:
            items = [
                t for t in items
                if float(t.get("download_rate", 0)) > 0 or float(t.get("upload_rate", 0)) > 0
            ]
        elif self.filter_tab == FilterTab.ERROR:
            items = [
                t for t in items
                if t.get("last_error") or (isinstance(t.get("errc"), int) and t["errc"] != 0) or t.get("error")
            ]
        elif self.filter_tab == FilterTab.CHECKING:
            items = [t for t in items if "check" in get_display_state(t).lower()]

        # Filter by Text Search
        q = self.search_query.strip().lower()
        if q:
            filtered = []
            for t in items:
                name = str(t.get("name", "")).lower()
                ih = str(t.get("info_hash", "")).lower()
                tags = str(t.get("spritzle.tags", "")).lower()
                if q in name or q in ih or q in tags:
                    filtered.append(t)
            items = filtered

        # Filter by Custom Query
        if self.custom_query:
            for part in self.custom_query.split():
                if "=" in part:
                    k, v = part.split("=", 1)
                    k = k.strip()
                    v = v.strip().lower()
                    if k == "state":
                        items = [t for t in items if get_display_state(t).lower() == v]
                    elif k in ("name", "info_hash"):
                        items = [t for t in items if v in str(t.get(k, "")).lower()]

        # Sorting
        def sort_key(t: Dict[str, Any]) -> Any:
            col = self.sort_column
            if col == "name":
                return (str(t.get("name") or "").lower(),)
            elif col == "state":
                return (get_display_state(t),)
            elif col == "progress":
                return (float(t.get("progress", 0.0)),)
            elif col == "size":
                return (float(t.get("total_wanted", 0) or t.get("total_size", 0)),)
            elif col == "done":
                return (float(t.get("total_done", 0)),)
            elif col == "download_rate":
                return (float(t.get("download_rate", 0)),)
            elif col == "upload_rate":
                return (float(t.get("upload_rate", 0)),)
            elif col == "peers":
                return (int(t.get("num_peers", 0)),)
            elif col == "seeds":
                return (int(t.get("num_seeds", 0)),)
            elif col == "eta":
                dl = float(t.get("download_rate", 0))
                wanted = float(t.get("total_wanted", 0) or t.get("total_size", 0))
                done = float(t.get("total_done", 0))
                if dl > 0 and wanted > done:
                    return ((wanted - done) / dl,)
                return (float("inf") if not self.sort_ascending else -1,)
            elif col == "ratio":
                up = float(t.get("all_time_upload", 0))
                dl = float(t.get("all_time_download", 0) or t.get("total_done", 0))
                return (up / dl if dl > 0 else 0.0,)
            elif col == "added":
                return (float(t.get("added_time", 0) or 0),)
            return (0,)

        reverse = not self.sort_ascending
        if self.sort_column == "name":
            reverse = self.sort_ascending

        try:
            items = sorted(items, key=sort_key, reverse=reverse)
        except Exception:
            pass

        return items

    def clamp_selection(self, items_count: int) -> None:
        if items_count == 0:
            self.selected_index = 0
            self.scroll_offset = 0
        else:
            self.selected_index = max(0, min(self.selected_index, items_count - 1))

    def move_selection(self, delta: int, items_count: int) -> None:
        if items_count == 0:
            return
        self.cursor_active = True
        if delta == -9999:  # Home
            self.selected_index = 0
        elif delta == 9999:  # End
            self.selected_index = items_count - 1
        else:
            self.selected_index = max(0, min(self.selected_index + delta, items_count - 1))

    def get_selected_torrent(self, items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not items:
            return None
        self.clamp_selection(len(items))
        return items[self.selected_index]

    def get_target_hashes(self, items: List[Dict[str, Any]]) -> List[str]:
        if self.selected_hashes:
            current_hashes = {t["info_hash"] for t in items if "info_hash" in t}
            targets = [h for h in self.selected_hashes if h in current_hashes]
            if targets:
                return targets
        selected = self.get_selected_torrent(items)
        if selected and "info_hash" in selected:
            return [selected["info_hash"]]
        return []

    def toggle_select_current(self, items: List[Dict[str, Any]]) -> None:
        self.cursor_active = True
        selected = self.get_selected_torrent(items)
        if not selected or "info_hash" not in selected:
            return
        ih = selected["info_hash"]
        if ih in self.selected_hashes:
            self.selected_hashes.remove(ih)
        else:
            self.selected_hashes.add(ih)

    def toggle_select_all(self, items: List[Dict[str, Any]]) -> None:
        current_hashes = {t["info_hash"] for t in items if "info_hash" in t}
        if current_hashes and self.selected_hashes >= current_hashes:
            self.selected_hashes.clear()
        else:
            self.selected_hashes = set(current_hashes)

    def cycle_filter_tab(self, forward: bool = True) -> None:
        tab_keys = [k for k, _, _ in FILTER_TABS]
        if self.filter_tab in tab_keys:
            idx = tab_keys.index(self.filter_tab)
            idx = (idx + 1) % len(tab_keys) if forward else (idx - 1) % len(tab_keys)
            self.filter_tab = tab_keys[idx]
        else:
            self.filter_tab = FilterTab.ALL
        self.selected_index = 0
        self.scroll_offset = 0

    def cycle_sort_column(self) -> None:
        valid_cols = [k for k, _, _, _ in ALL_COLUMNS]
        if self.sort_column in valid_cols:
            idx = (valid_cols.index(self.sort_column) + 1) % len(valid_cols)
            self.sort_column = valid_cols[idx]
        else:
            self.sort_column = "download_rate"
        self.sort_ascending = False

    def toggle_column(self, col: str) -> None:
        if col in self.visible_columns:
            if len(self.visible_columns) > 1:
                self.visible_columns.remove(col)
                self.set_status(f"Hidden column: {col}")
            else:
                self.set_status("Cannot hide all columns", is_error=True)
        else:
            valid_cols = [k for k, _, _, _ in ALL_COLUMNS]
            if col in valid_cols:
                self.visible_columns.append(col)
                self.set_status(f"Shown column: {col}")


# ---------------------------------------------------------------------------
# Background Actions
# ---------------------------------------------------------------------------

async def _batch_action(client, hashes: List[str], action: str) -> None:
    sem = asyncio.Semaphore(32)

    async def _do(ih: str) -> None:
        async with sem:
            url = client.url(f"torrent/{ih}/{action}")
            try:
                async with client.session.post(url, json=[]) as _:
                    pass
            except Exception:
                pass

    await asyncio.gather(*[_do(ih) for ih in hashes], return_exceptions=True)


async def _batch_delete(client, hashes: List[str], delete_files: bool = False) -> None:
    sem = asyncio.Semaphore(32)
    params = {"delete_files": ""} if delete_files else {}

    async def _do(ih: str) -> None:
        async with sem:
            url = client.url(f"torrent/{ih}")
            try:
                async with client.session.delete(url, params=params) as _:
                    pass
            except Exception:
                pass

    await asyncio.gather(*[_do(ih) for ih in hashes], return_exceptions=True)


async def _action_move(client, state: DashboardState, info_hash: str, new_path: str) -> None:
    try:
        url = client.url(f"torrent/{info_hash}/move_storage")
        async with client.session.post(url, json=[new_path]) as resp:
            if resp.status == 200:
                state.set_status(f"Moved storage to {new_path}")
            else:
                err = await resp.text()
                state.set_status(f"Move failed: {err[:50]}", is_error=True)
    except Exception as e:
        state.set_status(f"Move error: {e}", is_error=True)


async def _action_add(client, state: DashboardState, path_or_url: str) -> None:
    try:
        parsed = urlparse(path_or_url)
        if parsed.scheme in ("http", "https", "magnet"):
            async with client.session.post(client.url("torrent"), json={"url": path_or_url}) as resp:
                if resp.status in (200, 201):
                    state.set_status("Torrent added successfully")
                else:
                    err = await resp.text()
                    state.set_status(f"Error adding: {err[:50]}", is_error=True)
        else:
            path = Path(path_or_url).expanduser().resolve()
            if not path.is_file():
                state.set_status(f"File not found: {path_or_url}", is_error=True)
                return
            content = path.read_bytes()
            b64 = base64.b64encode(content).decode("ascii")
            async with client.session.post(client.url("torrent"), json={"torrent": b64}) as resp:
                if resp.status in (200, 201):
                    state.set_status(f"Added {path.name} successfully")
                else:
                    err = await resp.text()
                    state.set_status(f"Error adding: {err[:50]}", is_error=True)
    except Exception as e:
        state.set_status(f"Failed to add: {e}", is_error=True)


async def execute_command(cmd: str, client, state: DashboardState, quit_event: asyncio.Event) -> None:
    cmd = cmd.strip()
    if not cmd:
        return
    parts = cmd.split(maxsplit=1)
    action = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if action in (":q", ":quit", ":exit", "q", "quit", "exit"):
        quit_event.set()
        return

    items = state.get_filtered_items()

    if action in (":pause", "pause"):
        if arg == "all":
            all_hashes = [t["info_hash"] for t in state.raw_torrents if "info_hash" in t]
            await _batch_action(client, all_hashes, "pause")
            state.set_status(f"Paused all ({len(all_hashes)}) torrents")
        else:
            targets = state.get_target_hashes(items)
            if targets:
                await _batch_action(client, targets, "pause")
                state.set_status(f"Paused {len(targets)} torrent(s)")
                state.selected_hashes.clear()
            else:
                state.set_status("No torrent selected", is_error=True)

    elif action in (":resume", "resume"):
        if arg == "all":
            all_hashes = [t["info_hash"] for t in state.raw_torrents if "info_hash" in t]
            await _batch_action(client, all_hashes, "resume")
            state.set_status(f"Resumed all ({len(all_hashes)}) torrents")
        else:
            targets = state.get_target_hashes(items)
            if targets:
                await _batch_action(client, targets, "resume")
                state.set_status(f"Resumed {len(targets)} torrent(s)")
                state.selected_hashes.clear()
            else:
                state.set_status("No torrent selected", is_error=True)

    elif action in (":rm", ":remove", ":delete", "rm", "remove", "delete"):
        targets = state.get_target_hashes(items)
        if not targets:
            state.set_status("No torrent selected", is_error=True)
            return
        delete_files = "--delete-files" in arg or "-d" in arg

        async def _do_delete():
            await _batch_delete(client, targets, delete_files=delete_files)
            state.set_status(
                f"Removed {len(targets)} torrent(s)" + (" (files deleted)" if delete_files else "")
            )
            state.selected_hashes.clear()

        if not arg:
            count = len(targets)
            name_prev = (
                items[state.selected_index].get("name", "torrent")
                if count == 1 and state.selected_index < len(items)
                else f"{count} torrents"
            )
            state.confirm_prompt = f"Remove {name_prev}? [y/N] (D to delete files)"
            state.confirm_callback = _do_delete
            state.confirm_delete_callback = lambda: _batch_delete(client, targets, delete_files=True)
        else:
            await _do_delete()

    elif action in (":reannounce", "reannounce"):
        targets = state.get_target_hashes(items)
        if targets:
            await _batch_action(client, targets, "reannounce")
            state.set_status(f"Reannounced {len(targets)} torrent(s)")
        else:
            state.set_status("No torrent selected", is_error=True)

    elif action in (":add", "add"):
        if not arg:
            state.set_status("Usage: :add <url|magnet|path>", is_error=True)
            return
        await _action_add(client, state, arg)

    elif action in (":filter", ":f", "filter", "f"):
        if not arg or arg == "clear":
            state.custom_query = None
            state.set_status("Filter cleared")
        else:
            state.custom_query = arg
            state.set_status(f"Filter set: {arg}")

    elif action in (":search", ":s", "search", "s"):
        if not arg or arg == "clear":
            state.search_query = ""
            state.set_status("Search cleared")
        else:
            state.search_query = arg
            state.set_status(f"Search: {arg}")

    elif action in (":clear", "clear"):
        state.search_query = ""
        state.custom_query = None
        state.filter_tab = FilterTab.ALL
        state.selected_hashes.clear()
        state.set_status("Filters and search cleared")

    elif action in (":sort", "sort"):
        args = arg.split()
        if not args:
            cols = ", ".join(k for k, _, _, _ in ALL_COLUMNS)
            state.set_status(f"Available columns: {cols}")
            return
        col = args[0].lower()
        valid_cols = [k for k, _, _, _ in ALL_COLUMNS]
        if col in valid_cols:
            state.sort_column = col
            if len(args) > 1:
                state.sort_ascending = args[1].lower() in ("asc", "ascending", "true", "1")
            state.set_status(f"Sorting by {col} ({'asc' if state.sort_ascending else 'desc'})")
        else:
            state.set_status(f"Unknown column '{col}'. Valid: {', '.join(valid_cols)}", is_error=True)

    elif action in (":col", ":column", ":columns", "col", "column", "columns"):
        args = arg.split()
        if not args:
            state.view_mode = "columns"
            return
        sub = args[0]
        if sub == "reset":
            state.visible_columns = list(DEFAULT_COLUMNS)
            state.set_status("Columns reset to default")
        elif sub.startswith("+"):
            col = sub[1:].lower()
            valid_cols = [k for k, _, _, _ in ALL_COLUMNS]
            if col in valid_cols and col not in state.visible_columns:
                state.visible_columns.append(col)
                state.set_status(f"Added column {col}")
            else:
                state.set_status(f"Invalid or already visible column: {col}", is_error=True)
        elif sub.startswith("-"):
            col = sub[1:].lower()
            if col in state.visible_columns:
                if len(state.visible_columns) > 1:
                    state.visible_columns.remove(col)
                    state.set_status(f"Removed column {col}")
                else:
                    state.set_status("Cannot remove all columns", is_error=True)
            else:
                state.set_status(f"Column {col} not visible", is_error=True)
        else:
            state.set_status("Usage: :col +<name> | -<name> | reset", is_error=True)

    elif action in (":move", "move"):
        if not arg:
            state.set_status("Usage: :move <destination_path>", is_error=True)
            return
        targets = state.get_target_hashes(items)
        if targets:
            await _action_move(client, state, targets[0], arg)
        else:
            state.set_status("No torrent selected", is_error=True)

    elif action in (":help", ":h", "help", "h"):
        state.view_mode = "help"

    else:
        state.set_status(f"Unknown command: {action}. Type :help for help.", is_error=True)


# ---------------------------------------------------------------------------
# Rich Renderers
# ---------------------------------------------------------------------------

def _build_filter_bar_text(state: DashboardState, is_color: bool = True) -> Text:
    """Render the filter tabs bar."""
    bar = Text()
    for tab_id, label, key in FILTER_TABS:
        is_active = state.filter_tab == tab_id
        if is_active:
            if is_color:
                bar.append(f" [{key}:{label}] ", style=f"bold white on {BRAND_DARK}")
            else:
                bar.append(f" *[{label}]* ")
        else:
            if is_color:
                bar.append(f"  {key}:{label}  ", style="dim")
            else:
                bar.append(f"  {label}  ")

    if state.search_query:
        if is_color:
            bar.append(" │ Search: ", style="dim")
            bar.append(f'"{state.search_query}"', style="bold yellow")
        else:
            bar.append(f' | Search: "{state.search_query}"')

    if state.custom_query:
        if is_color:
            bar.append(" │ Filter: ", style="dim")
            bar.append(state.custom_query, style="bold magenta")
        else:
            bar.append(f" | Filter: {state.custom_query}")

    if state.selected_hashes:
        count = len(state.selected_hashes)
        if is_color:
            bar.append(" │ Selected: ", style="dim")
            bar.append(f"{count}", style="bold green")
        else:
            bar.append(f" | Selected: {count}")

    return bar


def _build_interactive_table(
    items: List[Dict[str, Any]],
    state: DashboardState,
    is_color: bool = True,
    max_rows: int = 15,
) -> Table:
    """Build the main selectable torrents table."""
    table = Table(
        box=None if not is_color else Table.grid().box,
        header_style=HEADER_STYLE,
        show_header=True,
        expand=True,
        caption_style="none",
    )

    col_meta: Dict[str, Tuple[str, Optional[int], Literal["left", "right", "center"]]] = {
        k: (lbl, ratio, justify) for k, lbl, ratio, justify in ALL_COLUMNS
    }

    # Add columns according to visible_columns
    for col_key in state.visible_columns:
        if col_key not in col_meta:
            continue
        label, ratio, justify = col_meta[col_key]
        if col_key == state.sort_column:
            sort_arrow = " ▲" if state.sort_ascending else " ▼"
            col_label = f"{label}{sort_arrow}"
        else:
            col_label = label

        if ratio == 1:
            table.add_column(col_label, ratio=1, min_width=14, justify=justify, no_wrap=True)
        else:
            table.add_column(col_label, justify=justify, no_wrap=True)

    if not items:
        table.add_row(
            "[dim]No matching torrents[/dim]" if is_color else "No matching torrents",
            *([""] * (len(table.columns) - 1)),
        )
        return table

    # Windowing / scrolling calculations
    state.clamp_selection(len(items))
    if state.selected_index < state.scroll_offset:
        state.scroll_offset = state.selected_index
    elif state.selected_index >= state.scroll_offset + max_rows:
        state.scroll_offset = state.selected_index - max_rows + 1

    visible_slice = items[state.scroll_offset : state.scroll_offset + max_rows]

    for idx, t in enumerate(visible_slice):
        actual_idx = state.scroll_offset + idx
        is_selected = state.cursor_active and (actual_idx == state.selected_index)
        ih = str(t.get("info_hash", ""))
        is_checked = ih in state.selected_hashes

        name = str(t.get("name") or ih or "torrent")
        st = get_display_state(t)
        progress = float(t.get("progress", 0.0))
        dl_rate = float(t.get("download_rate", 0))
        ul_rate = float(t.get("upload_rate", 0))
        total_wanted = float(t.get("total_wanted", 0) or t.get("total_size", 0))
        total_done = float(t.get("total_done", 0))
        num_peers = int(t.get("num_peers", 0))
        num_seeds = int(t.get("num_seeds", 0))

        if dl_rate > 0 and total_wanted > total_done:
            eta_sec = (total_wanted - total_done) / dl_rate
        else:
            eta_sec = None

        total_up = float(t.get("all_time_upload", 0))
        total_dl = float(t.get("all_time_download", 0) or total_done)
        ratio = (total_up / total_dl) if total_dl > 0 else 0.0

        # Cursor and checkbox prefix
        if is_selected:
            cursor_str = f"[bold {BRAND_ACCENT}]▸[/bold {BRAND_ACCENT}] " if is_color else "> "
        else:
            cursor_str = "  "

        if is_color:
            check_str = (
                f"[bold green]{escape('[x]')}[/bold green] "
                if is_checked
                else (f"[dim]{escape('[ ]')}[/dim] " if state.selected_hashes else "")
            )
        else:
            check_str = (
                escape("[x] ")
                if is_checked
                else (escape("[ ] ") if state.selected_hashes else "")
            )
        prefix = f"{cursor_str}{check_str}"
        name_disp = f"[bold {BRAND_ACCENT}]{escape(name)}[/bold {BRAND_ACCENT}]" if (is_selected and is_color) else escape(name)

        row_cells: List[str] = []
        for col_key in state.visible_columns:
            if col_key == "name":
                row_cells.append(f"{prefix}{name_disp}")
            elif col_key == "state":
                row_cells.append(format_state_pill(st, use_color=is_color))
            elif col_key == "progress":
                row_cells.append(
                    format_progress(
                        progress,
                        human=True,
                        width=10,
                        style="smooth" if is_color else "blocks",
                        use_color=is_color,
                    )
                )
            elif col_key == "size":
                row_cells.append(format_bytes(total_wanted))
            elif col_key == "done":
                row_cells.append(format_bytes(total_done))
            elif col_key == "download_rate":
                row_cells.append(format_speed(dl_rate, use_color=is_color))
            elif col_key == "upload_rate":
                row_cells.append(format_speed(ul_rate, use_color=is_color, is_upload=True))
            elif col_key == "peers":
                row_cells.append(f"{num_peers} ({num_seeds})")
            elif col_key == "seeds":
                row_cells.append(str(num_seeds))
            elif col_key == "eta":
                row_cells.append(format_eta(eta_sec))
            elif col_key == "ratio":
                row_cells.append(f"{ratio:.2f}")
            elif col_key == "tags":
                tags = t.get("spritzle.tags", [])
                tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
                row_cells.append(escape(tags_str))

        if (is_selected or is_checked) and is_color:
            table.add_row(*row_cells, style="bold")
        else:
            table.add_row(*row_cells)

    return table


def _build_inspector_panel(state: DashboardState, is_color: bool = True) -> Panel:
    """Build the detailed torrent inspector view."""
    data = state.inspector_data or {}
    name = data.get("name") or "Torrent Details"
    info_hash = data.get("info_hash") or ""
    current_tab = state.inspector_tab

    tabs_header = Text()
    tabs = [
        ("summary", "1: Summary"),
        ("files", f"2: Files ({len(state.inspector_files)})"),
        ("trackers", f"3: Trackers ({len(state.inspector_trackers)})"),
        ("peers", f"4: Peers ({len(state.inspector_peers)})"),
    ]
    for tab_id, label in tabs:
        if tab_id == current_tab:
            tabs_header.append(f" [{label}] ", style=f"bold white on {BRAND_DARK}" if is_color else "bold")
        else:
            tabs_header.append(f"  {label}  ", style="dim" if is_color else "")

    content: Any = ""
    if current_tab == "summary":
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim", no_wrap=True, width=16)
        grid.add_column()
        grid.add_column(style="dim", no_wrap=True, width=16)
        grid.add_column()

        st = get_display_state(data)
        progress = float(data.get("progress", 0.0))
        dl_rate = float(data.get("download_rate", 0))
        ul_rate = float(data.get("upload_rate", 0))
        total_wanted = float(data.get("total_wanted", 0) or data.get("total_size", 0))
        total_done = float(data.get("total_done", 0))
        num_peers = int(data.get("num_peers", 0))
        num_seeds = int(data.get("num_seeds", 0))
        save_path = data.get("save_path", "")
        tags = data.get("spritzle.tags", [])
        tags_str = ", ".join(tags) if isinstance(tags, list) and tags else "<none>"

        total_up = float(data.get("all_time_upload", 0))
        total_dl = float(data.get("all_time_download", 0) or total_done)
        ratio = (total_up / total_dl) if total_dl > 0 else 0.0

        num_pieces = data.get("num_pieces", 0)
        total_pieces = data.get("total_pieces", 0)
        piece_len = data.get("piece_length", 0)
        pieces_str = f"{num_pieces} / {total_pieces}" + (f" ({format_bytes(piece_len)})" if piece_len else "")

        added_str = format_datetime(data.get("added_time"))
        completed_str = format_datetime(data.get("completed_time")) if data.get("completed_time") else "--"

        grid.add_row("Status:", format_state_pill(st, use_color=is_color, peers=num_peers), "Info Hash:", f"[{BRAND_ACCENT}]{info_hash}[/{BRAND_ACCENT}]" if is_color else info_hash)
        grid.add_row("Progress:", f"{format_progress(progress, human=True, width=15, use_color=is_color)}", "Save Path:", escape(str(save_path)))
        grid.add_row("Downloaded:", f"{format_bytes(total_done)} / {format_bytes(total_wanted)}", "Peers / Seeds:", f"{num_peers} peers ({num_seeds} seeds)")
        grid.add_row("Speed:", f"{format_speed(dl_rate, use_color=is_color)}  {format_speed(ul_rate, use_color=is_color, is_upload=True)}", "Ratio:", f"{ratio:.2f}")
        grid.add_row("Pieces:", pieces_str, "Tags:", escape(tags_str))
        grid.add_row("Added:", added_str, "Completed:", completed_str)

        err_str = data.get("last_error") or data.get("error")
        if err_str:
            grid.add_row("Error:", f"[bold red]{escape(str(err_str))}[/bold red]", "", "")

        content = grid

    elif current_tab == "files":
        f_table = Table(box=box.SIMPLE, show_header=True, header_style=HEADER_STYLE, expand=True)
        f_table.add_column("#", width=4, justify="right")
        f_table.add_column("Path", ratio=1, no_wrap=True)
        f_table.add_column("Size", width=10, justify="right")
        f_table.add_column("Progress", width=12)
        f_table.add_column("Priority", width=10)

        if not state.inspector_files:
            f_table.add_row("", "[dim]No file details loaded[/dim]", "", "", "")
        else:
            for idx, f in enumerate(state.inspector_files[:25]):
                f_path = str(f.get("path") or f.get("name") or "")
                f_size = float(f.get("size", 0))
                f_prog = float(f.get("progress", 0.0))
                prio = f.get("priority", 1)
                prio_str = "Skip" if prio == 0 else f"Prio {prio}"
                f_table.add_row(
                    str(idx),
                    escape(f_path),
                    format_bytes(f_size),
                    format_progress(f_prog, human=True, width=8, use_color=is_color),
                    prio_str,
                )
        content = f_table

    elif current_tab == "trackers":
        t_table = Table(box=box.SIMPLE, show_header=True, header_style=HEADER_STYLE, expand=True)
        t_table.add_column("Tier", width=6, justify="right")
        t_table.add_column("URL", ratio=1, no_wrap=True)
        t_table.add_column("Status", width=12)
        t_table.add_column("Seeds", width=8, justify="right")
        t_table.add_column("Peers", width=8, justify="right")
        t_table.add_column("Next Announce", width=14, justify="right")

        if not state.inspector_trackers:
            t_table.add_row("", "[dim]No tracker details loaded[/dim]", "", "", "", "")
        else:
            for trk in state.inspector_trackers[:25]:
                tier = str(trk.get("tier", 0))
                url = str(trk.get("url", ""))
                status = str(trk.get("status", "working"))
                seeds = str(trk.get("seeds", trk.get("num_seeds", "-")))
                peers = str(trk.get("peers", trk.get("num_peers", "-")))
                next_ann = str(trk.get("next_announce", "-"))
                t_table.add_row(tier, escape(url), status, seeds, peers, next_ann)
        content = t_table

    elif current_tab == "peers":
        p_table = Table(box=box.SIMPLE, show_header=True, header_style=HEADER_STYLE, expand=True)
        p_table.add_column("IP:Port", width=22, no_wrap=True)
        p_table.add_column("Client", ratio=1, no_wrap=True)
        p_table.add_column("Down Speed", width=12, justify="right")
        p_table.add_column("Up Speed", width=12, justify="right")
        p_table.add_column("Progress", width=10)
        p_table.add_column("Flags", width=10)

        if not state.inspector_peers:
            p_table.add_row("", "[dim]No connected peers[/dim]", "", "", "", "")
        else:
            for p in state.inspector_peers[:25]:
                ip = str(p.get("ip") or p.get("address", ""))
                client_id = str(p.get("client") or "")
                dl = float(p.get("download_rate", 0))
                ul = float(p.get("upload_rate", 0))
                prog = float(p.get("progress", 0.0))
                flags = str(p.get("flags", ""))
                p_table.add_row(
                    escape(ip),
                    escape(client_id),
                    format_speed(dl, use_color=is_color),
                    format_speed(ul, use_color=is_color, is_upload=True),
                    f"{prog * 100:.1f}%",
                    flags,
                )
        content = p_table

    return Panel(
        Group(
            tabs_header,
            "",
            content,
        ),
        title=f"[bold]Torrent Inspector: {escape(name)}[/bold]" if is_color else f"Torrent Inspector: {name}",
        subtitle="[dim]Press Esc/i to return │ Tab/1-4: Switch Tabs[/dim]",
        border_style=BRAND_PRIMARY if is_color else "none",
    )


def _build_help_panel(is_color: bool = True) -> Panel:
    """Build the keybindings and commands cheat sheet."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=f"bold {BRAND_ACCENT}", width=16)
    grid.add_column(style="white")

    grid.add_row("[bold yellow]Navigation[/bold yellow]", "")
    grid.add_row("↑ / ↓ / j / k", "Move selection cursor up / down")
    grid.add_row("Home / End / g / G", "Jump to top / bottom")
    grid.add_row("PgUp / PgDn", "Scroll 10 items up / down")
    grid.add_row("Space", "Toggle selection checkbox on current item")
    grid.add_row("*", "Select / deselect all items")
    grid.add_row("Enter / i", "Open / close detailed torrent inspector")
    grid.add_row("", "")

    grid.add_row("[bold yellow]Filter Tabs[/bold yellow]", "")
    grid.add_row("1 - 7", "Switch filter tab: All, DL, Seed, Paused, Active, Error, Checking")
    grid.add_row("Tab / Shift-Tab", "Cycle filter tabs forward / backward")
    grid.add_row("/", "Search torrents by name, hash, or tags")
    grid.add_row("Esc", "Clear search filter / return to main list")
    grid.add_row("", "")

    grid.add_row("[bold yellow]Actions[/bold yellow]", "")
    grid.add_row("p", "Pause selected torrent(s)")
    grid.add_row("r", "Resume selected torrent(s)")
    grid.add_row("d / x", "Delete selected torrent(s) (prompts confirmation, D deletes files)")
    grid.add_row("a", "Force reannounce selected torrent(s) to trackers")
    grid.add_row("", "")

    grid.add_row("[bold yellow]Sorting & Columns[/bold yellow]", "")
    grid.add_row("o / s", "Cycle sort column (Name, Speed, Progress, Size, ETA, etc.)")
    grid.add_row("R", "Reverse sort order (Ascending <-> Descending)")
    grid.add_row("c", "Open column visibility selector")
    grid.add_row("", "")

    grid.add_row("[bold yellow]Command Prompt (:)[/bold yellow]", "")
    grid.add_row(":pause [all]", "Pause current or all torrents")
    grid.add_row(":resume [all]", "Resume current or all torrents")
    grid.add_row(":rm [-d]", "Remove torrent(s) (-d to delete files)")
    grid.add_row(":add <url|file>", "Add a new torrent directly to daemon")
    grid.add_row(":filter <query>", "Apply field query filter (e.g. :filter total_size.gt=1G)")
    grid.add_row(":sort <col> [asc|desc]", "Set sort column and direction")
    grid.add_row(":col <+col|-col|reset>", "Add, remove, or reset table columns")
    grid.add_row(":move <destination>", "Move storage of selected torrent")
    grid.add_row(":q / :quit", "Exit dashboard")

    return Panel(
        grid,
        title="[bold]Spritzle Interactive Dashboard Help[/bold]" if is_color else "Spritzle Interactive Dashboard Help",
        subtitle="[dim]Press Esc, q, or ? to return to list[/dim]",
        border_style="yellow" if is_color else "none",
    )


def _build_columns_panel(state: DashboardState, is_color: bool = True) -> Panel:
    """Build the column customization modal."""
    table = Table(box=box.SIMPLE, show_header=True, header_style=HEADER_STYLE, expand=True)
    table.add_column("Key", width=6, justify="center")
    table.add_column("Column", width=18)
    table.add_column("Status", width=12)

    keys = "123456789abcdefgh"
    for idx, (col_id, label, _, _) in enumerate(ALL_COLUMNS):
        k = keys[idx] if idx < len(keys) else "-"
        is_visible = col_id in state.visible_columns
        status = "[bold green][x] Visible[/bold green]" if is_visible else "[dim][ ] Hidden[/dim]"
        prefix = "> " if idx == state.column_cursor else "  "
        table.add_row(
            f"{prefix}[bold]{k}[/bold]",
            label,
            status if is_color else ("[x] Visible" if is_visible else "[ ] Hidden"),
        )

    return Panel(
        table,
        title="[bold]Customize Visible Columns[/bold]" if is_color else "Customize Visible Columns",
        subtitle="[dim]Press key or Space to toggle │ ↑/↓: Move │ Esc/Enter/q: Close[/dim]",
        border_style=BRAND_PRIMARY if is_color else "none",
    )


def _build_footer_status(state: DashboardState, is_color: bool = True) -> Any:
    """Build footer status line, prompt, or feedback message."""
    if state.confirm_prompt:
        return Panel(
            f"[bold yellow]⚠ {escape(state.confirm_prompt)}[/bold yellow]" if is_color else f"⚠ {state.confirm_prompt}",
            box=box.SQUARE,
            style="none",
        )
    elif state.command_mode:
        pre = escape(state.command_buffer[: state.command_cursor])
        cur = (
            escape(state.command_buffer[state.command_cursor : state.command_cursor + 1])
            if state.command_cursor < len(state.command_buffer)
            else " "
        )
        post = (
            escape(state.command_buffer[state.command_cursor + 1 :])
            if state.command_cursor < len(state.command_buffer)
            else ""
        )
        prompt_txt = (
            f":[bold {BRAND_ACCENT}]{pre}[/bold {BRAND_ACCENT}][reverse]{cur}[/reverse][bold {BRAND_ACCENT}]{post}[/bold {BRAND_ACCENT}]"
            if is_color
            else f":{state.command_buffer}"
        )
        return Panel(prompt_txt, box=box.SQUARE)
    elif state.search_mode:
        prompt_txt = (
            f"/[bold yellow]{escape(state.search_buffer)}[/bold yellow][reverse] [/reverse]"
            if is_color
            else f"/{state.search_buffer}"
        )
        return Panel(prompt_txt, box=box.SQUARE)
    elif state.status_message:
        icon = "✖" if state.status_is_error else "✔"
        color = "bold red" if state.status_is_error else "bold green"
        msg = f"[{color}]{icon} {escape(state.status_message)}[/{color}]" if is_color else f"{icon} {state.status_message}"
        return Panel(msg, box=box.SQUARE)
    else:
        if state.selected_hashes:
            count = len(state.selected_hashes)
            hint = (
                f"[bold {BRAND_ACCENT}]{count} selected[/bold {BRAND_ACCENT}] [dim]│ Space:Deselect  *:All/None  p:Pause  r:Resume  d:Delete  Esc:Clear[/dim]"
                if is_color
                else f"{count} selected | Space:Deselect  *:All/None  p:Pause  r:Resume  d:Delete  Esc:Clear"
            )
        else:
            hint = (
                "[dim]q:Quit  ↑/↓:Move  Space:Select  p:Pause  r:Resume  d:Delete  i:Info  /:Search  ::Cmd  ?:Help[/dim]"
                if is_color
                else "q:Quit  Move:arrows/jk  Space:Select  p:Pause  r:Resume  d:Delete  i:Info  /:Search  ::Cmd  ?:Help"
            )
        return hint


def build_dashboard_renderable(
    items: List[Dict[str, Any]],
    stats: Dict[str, Any],
    is_color: bool = True,
    height: Optional[int] = None,
    state: Optional[DashboardState] = None,
) -> Panel:
    """Build the Rich renderable for spritzle top / list --watch."""
    dht_nodes = int(stats.get("dht.dht_nodes", 0))
    connected_peers = int(stats.get("peer.num_peers_connected", 0))
    total_dl = sum(float(t.get("download_rate", 0)) for t in items)
    total_ul = sum(float(t.get("upload_rate", 0)) for t in items)

    num_dl = sum(1 for t in items if get_display_state(t) == "downloading")
    num_seed = sum(1 for t in items if get_display_state(t) == "seeding")

    if dht_nodes < 10:
        dht_disp = (
            f"[yellow]●[/yellow] {dht_nodes} (bootstrapping DHT...)"
            if is_color
            else f"{dht_nodes} (bootstrapping DHT...)"
        )
    else:
        dht_disp = f"[magenta]● {dht_nodes} nodes[/magenta]" if is_color else f"{dht_nodes}"

    header_text = (
        f"▼ DL: [bold green]{format_speed(total_dl)}[/bold green]  "
        f"▲ UL: [bold blue]{format_speed(total_ul)}[/bold blue]  │  "
        f"Peers: [bold]{connected_peers}[/bold]  │  "
        f"Torrents: [green]● {num_dl} downloading[/green], [blue]● {num_seed} seeding[/blue]  │  "
        f"DHT: {dht_disp}"
    ) if is_color else (
        f"DL: {format_speed(total_dl)}  UL: {format_speed(total_ul)}  |  "
        f"Peers: {connected_peers}  |  "
        f"Torrents: {num_dl} downloading, {num_seed} seeding  |  "
        f"DHT: {dht_disp}"
    )

    if state is None:
        # Non-interactive / backward-compatible table rendering
        table = Table(
            box=None if not is_color else Table.grid().box,
            header_style=HEADER_STYLE,
            show_header=True,
            expand=True,
            caption_style="none",
        )
        table.add_column("Name", ratio=1, min_width=12, no_wrap=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Progress", no_wrap=True)
        table.add_column("Size", justify="right", no_wrap=True)
        table.add_column("Down Speed", justify="right", no_wrap=True)
        table.add_column("Up Speed", justify="right", no_wrap=True)
        table.add_column("Peers", justify="right", no_wrap=True)
        table.add_column("ETA", justify="right", no_wrap=True)

        if not items:
            table.add_row("[dim]No active torrents[/dim]" if is_color else "No active torrents", "", "", "", "", "", "", "")
        else:
            for t in items:
                name = t.get("name") or t.get("info_hash", "torrent")
                st_str = get_display_state(t)
                prog_val = float(t.get("progress", 0.0))
                dl_val = float(t.get("download_rate", 0))
                ul_val = float(t.get("upload_rate", 0))
                wanted_val = float(t.get("total_wanted", 0) or t.get("total_size", 0))
                done_val = float(t.get("total_done", 0))
                p_cnt = int(t.get("num_peers", 0))
                s_cnt = int(t.get("num_seeds", 0))

                eta_v = (wanted_val - done_val) / dl_val if dl_val > 0 and wanted_val > done_val else None

                table.add_row(
                    escape(str(name)),
                    format_state_pill(st_str, use_color=is_color),
                    format_progress(
                        prog_val, human=True, width=10, style="smooth" if is_color else "blocks", use_color=is_color
                    ),
                    format_bytes(wanted_val),
                    format_speed(dl_val, use_color=is_color),
                    format_speed(ul_val, use_color=is_color, is_upload=True),
                    f"{p_cnt} ({s_cnt})",
                    format_eta(eta_v),
                )

        return Panel(
            Group(
                header_text if isinstance(header_text, str) else str(header_text),
                "",
                table,
            ),
            title="[bold]Spritzle Torrent Monitor[/bold]" if is_color else "Spritzle Torrent Monitor",
            subtitle="[dim]Press 'q' or Ctrl+C to exit[/dim]" if is_color else "Press 'q' or Ctrl+C to exit",
            border_style="dim" if is_color else "none",
            height=height,
        )

    # Interactive Dashboard Mode
    filter_bar = _build_filter_bar_text(state, is_color)
    max_table_rows = max(3, (height or 24) - 9)

    if state.view_mode == "inspector":
        body = _build_inspector_panel(state, is_color)
    elif state.view_mode == "help":
        body = _build_help_panel(is_color)
    elif state.view_mode == "columns":
        body = _build_columns_panel(state, is_color)
    else:
        body = _build_interactive_table(items, state, is_color, max_rows=max_table_rows)

    footer = _build_footer_status(state, is_color)

    return Panel(
        Group(
            header_text,
            filter_bar,
            "",
            body,
            "",
            footer,
        ),
        title="[bold]Spritzle Torrent Monitor[/bold]" if is_color else "Spritzle Torrent Monitor",
        subtitle="[dim]Press 'q' or Ctrl+C to exit[/dim]" if is_color else "Press 'q' or Ctrl+C to exit",
        border_style="dim" if is_color else "none",
        height=height,
    )


# ---------------------------------------------------------------------------
# Key Handler & Interactive Dashboard Loop
# ---------------------------------------------------------------------------

async def _load_inspector_data(client, state: DashboardState, info_hash: str) -> None:
    """Asynchronously load details for the selected torrent."""
    detail = await fetch_torrent_detail(client, info_hash)
    if detail:
        state.inspector_data = detail
    files, trackers, peers = await asyncio.gather(
        fetch_torrent_files(client, info_hash),
        fetch_torrent_trackers(client, info_hash),
        fetch_torrent_peers(client, info_hash),
        return_exceptions=True,
    )
    if isinstance(files, list):
        state.inspector_files = files
    if isinstance(trackers, list):
        state.inspector_trackers = trackers
    if isinstance(peers, list):
        state.inspector_peers = peers


async def handle_key_input(
    key: str,
    client: Any,
    state: DashboardState,
    quit_event: asyncio.Event,
    background_tasks: Set[asyncio.Task[Any]],
) -> None:
    """Dispatch a single keyboard event to the active dashboard mode."""
    # 1. Confirmation Prompt Mode
    if state.confirm_prompt is not None:
        if key in ("y", "Y"):
            cb = state.confirm_callback
            state.confirm_prompt = None
            state.confirm_callback = None
            state.confirm_delete_callback = None
            if cb:
                t = asyncio.create_task(cb())
                background_tasks.add(t)
                t.add_done_callback(background_tasks.discard)
        elif key in ("d", "D"):
            cb = state.confirm_delete_callback or state.confirm_callback
            state.confirm_prompt = None
            state.confirm_callback = None
            state.confirm_delete_callback = None
            if cb:
                t = asyncio.create_task(cb())
                background_tasks.add(t)
                t.add_done_callback(background_tasks.discard)
        elif key in ("n", "N", "escape", "q"):
            state.confirm_prompt = None
            state.confirm_callback = None
            state.confirm_delete_callback = None
            state.set_status("Action cancelled")
        return

    # 2. Command Prompt Mode
    if state.command_mode:
        if key == "enter":
            cmd = state.command_buffer
            state.command_mode = False
            state.command_buffer = ""
            state.command_cursor = 0
            if cmd:
                state.command_history.append(cmd)
                state.command_history_idx = -1
                t = asyncio.create_task(execute_command(cmd, client, state, quit_event))
                background_tasks.add(t)
                t.add_done_callback(background_tasks.discard)
        elif key == "escape":
            state.command_mode = False
            state.command_buffer = ""
            state.command_cursor = 0
        elif key == "backspace":
            if state.command_cursor > 0:
                state.command_buffer = (
                    state.command_buffer[: state.command_cursor - 1]
                    + state.command_buffer[state.command_cursor :]
                )
                state.command_cursor -= 1
        elif key == "delete":
            if state.command_cursor < len(state.command_buffer):
                state.command_buffer = (
                    state.command_buffer[: state.command_cursor]
                    + state.command_buffer[state.command_cursor + 1 :]
                )
        elif key == "left":
            state.command_cursor = max(0, state.command_cursor - 1)
        elif key == "right":
            state.command_cursor = min(len(state.command_buffer), state.command_cursor + 1)
        elif key == "home":
            state.command_cursor = 0
        elif key == "end":
            state.command_cursor = len(state.command_buffer)
        elif key == "up":
            if state.command_history:
                if state.command_history_idx == -1:
                    state.command_history_idx = len(state.command_history) - 1
                else:
                    state.command_history_idx = max(0, state.command_history_idx - 1)
                state.command_buffer = state.command_history[state.command_history_idx]
                state.command_cursor = len(state.command_buffer)
        elif key == "down":
            if state.command_history and state.command_history_idx != -1:
                if state.command_history_idx < len(state.command_history) - 1:
                    state.command_history_idx += 1
                    state.command_buffer = state.command_history[state.command_history_idx]
                    state.command_cursor = len(state.command_buffer)
                else:
                    state.command_history_idx = -1
                    state.command_buffer = ""
                    state.command_cursor = 0
        elif len(key) == 1:
            state.command_buffer = (
                state.command_buffer[: state.command_cursor]
                + key
                + state.command_buffer[state.command_cursor :]
            )
            state.command_cursor += 1
        return

    # 3. Search Mode
    if state.search_mode:
        if key == "enter":
            state.search_mode = False
        elif key == "escape":
            state.search_mode = False
            state.search_buffer = ""
            state.search_query = ""
        elif key == "backspace":
            state.search_buffer = state.search_buffer[:-1]
            state.search_query = state.search_buffer
        elif len(key) == 1:
            state.search_buffer += key
            state.search_query = state.search_buffer
        return

    # 4. Help View Mode
    if state.view_mode == "help":
        if key in ("escape", "q", "h", "?", "enter", "backspace"):
            state.view_mode = "list"
        return

    # 5. Columns View Mode
    if state.view_mode == "columns":
        keys = "123456789abcdefgh"
        if key in ("up", "k"):
            state.column_cursor = max(0, state.column_cursor - 1)
            return
        elif key in ("down", "j"):
            state.column_cursor = min(len(ALL_COLUMNS) - 1, state.column_cursor + 1)
            return
        elif key == " ":
            if 0 <= state.column_cursor < len(ALL_COLUMNS):
                col_id = ALL_COLUMNS[state.column_cursor][0]
                state.toggle_column(col_id)
            return
        elif key in keys:
            idx = keys.index(key)
            if idx < len(ALL_COLUMNS):
                col_id = ALL_COLUMNS[idx][0]
                state.toggle_column(col_id)
            return
        elif key in ("escape", "q", "enter"):
            state.view_mode = "list"
            return
        return

    # 6. Inspector View Mode
    if state.view_mode == "inspector":
        if key in ("escape", "q", "i", "enter", "backspace"):
            state.view_mode = "list"
        elif key == "1":
            state.inspector_tab = "summary"
        elif key == "2":
            state.inspector_tab = "files"
        elif key == "3":
            state.inspector_tab = "trackers"
        elif key == "4":
            state.inspector_tab = "peers"
        elif key in ("tab", "right"):
            tabs = ["summary", "files", "trackers", "peers"]
            idx = (tabs.index(state.inspector_tab) + 1) % len(tabs)
            state.inspector_tab = tabs[idx]
        elif key in ("shift_tab", "left"):
            tabs = ["summary", "files", "trackers", "peers"]
            idx = (tabs.index(state.inspector_tab) - 1) % len(tabs)
            state.inspector_tab = tabs[idx]
        return

    # 7. List Navigation Mode
    items = state.get_filtered_items()

    if key in ("up", "k"):
        state.move_selection(-1, len(items))
    elif key in ("down", "j"):
        state.move_selection(1, len(items))
    elif key == "page_up":
        state.move_selection(-10, len(items))
    elif key == "page_down":
        state.move_selection(10, len(items))
    elif key in ("home", "g"):
        state.move_selection(-9999, len(items))
    elif key in ("end", "G"):
        state.move_selection(9999, len(items))
    elif key == " ":
        state.toggle_select_current(items)
    elif key == "*":
        state.toggle_select_all(items)
    elif key in ("enter", "i", "v"):
        state.cursor_active = True
        selected = state.get_selected_torrent(items)
        if selected and "info_hash" in selected:
            state.view_mode = "inspector"
            state.inspector_tab = "summary"
            state.inspector_data = dict(selected)
            t = asyncio.create_task(_load_inspector_data(client, state, selected["info_hash"]))
            background_tasks.add(t)
            t.add_done_callback(background_tasks.discard)
    elif key == "1":
        state.filter_tab = FilterTab.ALL
        state.selected_index = 0
    elif key == "2":
        state.filter_tab = FilterTab.DOWNLOADING
        state.selected_index = 0
    elif key == "3":
        state.filter_tab = FilterTab.SEEDING
        state.selected_index = 0
    elif key == "4":
        state.filter_tab = FilterTab.PAUSED
        state.selected_index = 0
    elif key == "5":
        state.filter_tab = FilterTab.ACTIVE
        state.selected_index = 0
    elif key == "6":
        state.filter_tab = FilterTab.ERROR
        state.selected_index = 0
    elif key == "7":
        state.filter_tab = FilterTab.CHECKING
        state.selected_index = 0
    elif key == "tab":
        state.cycle_filter_tab(forward=True)
    elif key == "shift_tab":
        state.cycle_filter_tab(forward=False)
    elif key == "/":
        state.search_mode = True
        state.search_buffer = ""
    elif key == ":":
        state.command_mode = True
        state.command_buffer = ""
        state.command_cursor = 0
    elif key in ("o", "s"):
        state.cycle_sort_column()
    elif key == "R":
        state.sort_ascending = not state.sort_ascending
    elif key == "n":
        state.sort_column = "name"
    elif key == "P":
        state.sort_column = "progress"
    elif key == "D":
        state.sort_column = "download_rate"
    elif key == "U":
        state.sort_column = "upload_rate"
    elif key == "Z":
        state.sort_column = "size"
    elif key == "E":
        state.sort_column = "eta"
    elif key == "c":
        state.view_mode = "columns"
        state.column_cursor = 0
    elif key == "p":
        targets = state.get_target_hashes(items) if (state.cursor_active or state.selected_hashes) else []
        if targets:
            state.set_status(f"Pausing {len(targets)} torrent(s)...")

            async def _run_p():
                await _batch_action(client, targets, "pause")
                state.set_status(f"Paused {len(targets)} torrent(s)")
                state.selected_hashes.clear()

            t = asyncio.create_task(_run_p())
            background_tasks.add(t)
            t.add_done_callback(background_tasks.discard)
        else:
            state.set_status("No torrent selected", is_error=True)
    elif key == "r":
        targets = state.get_target_hashes(items) if (state.cursor_active or state.selected_hashes) else []
        if targets:
            state.set_status(f"Resuming {len(targets)} torrent(s)...")

            async def _run_r():
                await _batch_action(client, targets, "resume")
                state.set_status(f"Resumed {len(targets)} torrent(s)")
                state.selected_hashes.clear()

            t = asyncio.create_task(_run_r())
            background_tasks.add(t)
            t.add_done_callback(background_tasks.discard)
        else:
            state.set_status("No torrent selected", is_error=True)
    elif key in ("d", "x", "delete"):
        targets = state.get_target_hashes(items) if (state.cursor_active or state.selected_hashes) else []
        if targets:
            count = len(targets)
            name_prev = (
                items[state.selected_index].get("name", "torrent")
                if count == 1 and state.selected_index < len(items)
                else f"{count} torrents"
            )
            state.confirm_prompt = f"Remove {name_prev}? [y/N] (D to delete files)"

            async def _do_delete():
                await _batch_delete(client, targets, delete_files=False)
                state.set_status(f"Removed {count} torrent(s)")
                state.selected_hashes.clear()

            async def _do_delete_files():
                await _batch_delete(client, targets, delete_files=True)
                state.set_status(f"Removed {count} torrent(s) (files deleted)")
                state.selected_hashes.clear()

            state.confirm_callback = _do_delete
            state.confirm_delete_callback = _do_delete_files
        else:
            state.set_status("No torrent selected", is_error=True)
    elif key == "a":
        targets = state.get_target_hashes(items) if (state.cursor_active or state.selected_hashes) else []
        if targets:
            t = asyncio.create_task(_batch_action(client, targets, "reannounce"))
            background_tasks.add(t)
            t.add_done_callback(background_tasks.discard)
            state.set_status(f"Reannounced {len(targets)} torrent(s)")
        else:
            state.set_status("No torrent selected", is_error=True)
    elif key in ("?", "h"):
        state.view_mode = "help"
    elif key == "escape":
        if state.search_query:
            state.search_query = ""
            state.search_buffer = ""
        elif state.selected_hashes:
            state.selected_hashes.clear()
        elif state.cursor_active:
            state.cursor_active = False
        elif state.custom_query:
            state.custom_query = None
    elif key in ("q", "Q", "ctrl_c"):
        quit_event.set()


async def _sleep_or_quit(interval: float, quit_event: Optional[asyncio.Event]) -> bool:
    """Sleep for up to `interval` seconds, returning True if quit_event is set."""
    if quit_event is None:
        await asyncio.sleep(interval)
        return False
    if quit_event.is_set():
        return True

    if interval <= 0.05:
        await asyncio.sleep(interval)
        return quit_event.is_set()

    loop = asyncio.get_running_loop()
    end_time = loop.time() + interval
    while loop.time() < end_time:
        if quit_event.is_set():
            return True
        step = min(0.05, max(0.0, end_time - loop.time()))
        await asyncio.sleep(step)
    return quit_event.is_set()


async def run_dashboard(
    client,
    query: Optional[Sequence[str]] = None,
    interval: float = 1.0,
    color_opt: Optional[bool] = None,
    plain: bool = False,
    once: bool = False,
    quit_event: Optional[asyncio.Event] = None,
    fullscreen: bool = True,
) -> None:
    """Run an interactive updating Rich dashboard (spritzle top / list --watch)."""
    is_interactive = should_use_color(color_opt) and not plain
    console = get_console(color_opt)
    effective_quit = quit_event if quit_event is not None else asyncio.Event()

    try:
        if not is_interactive:
            # Plain / Non-interactive output mode
            async with KeyPressWatcher(quit_event=effective_quit):
                while True:
                    items = await fetch_torrents_with_status(client, query)
                    stats = await fetch_session_stats(client)
                    dht_nodes = int(stats.get("dht.dht_nodes", 0))
                    dht_str = f"{dht_nodes} (bootstrapping DHT...)" if dht_nodes < 10 else f"{dht_nodes}"
                    total_dl = sum(float(t.get("download_rate", 0)) for t in items)
                    total_ul = sum(float(t.get("upload_rate", 0)) for t in items)
                    print(
                        f"--- Spritzle Monitor | DL: {format_speed(total_dl)} | UL: {format_speed(total_ul)} | DHT: {dht_str} ---"
                    )
                    if not items:
                        print("No active torrents.")
                    else:
                        for t in items:
                            name = t.get("name") or t.get("info_hash", "torrent")
                            pct = f"{float(t.get('progress', 0.0)) * 100:.1f}%"
                            st = get_display_state(t)
                            dl = format_speed(t.get("download_rate", 0))
                            ul = format_speed(t.get("upload_rate", 0))
                            peers = t.get("num_peers", 0)
                            print(f"{name}\t{st}\t{pct}\t{dl}\t{ul}\t{peers}")

                    if once:
                        break
                    if await _sleep_or_quit(interval, effective_quit):
                        break
            return

        # Interactive Mode
        state = DashboardState(query=query)
        key_queue: asyncio.Queue[str] = asyncio.Queue()
        background_tasks: Set[asyncio.Task[Any]] = set()

        async with KeyPressWatcher(quit_event=effective_quit, key_queue=key_queue):
            # Initial fetch
            items = await fetch_torrents_with_status(client, query)
            stats = await fetch_session_stats(client)
            state.raw_torrents = items
            state.session_stats = stats

            async def poll_worker():
                while not effective_quit.is_set():
                    try:
                        await asyncio.sleep(interval)
                        if effective_quit.is_set():
                            break
                        fresh_items = await fetch_torrents_with_status(client, query)
                        fresh_stats = await fetch_session_stats(client)
                        state.raw_torrents = fresh_items
                        state.session_stats = fresh_stats

                        # If in inspector mode, refresh current torrent detail
                        if state.view_mode == "inspector":
                            sel = state.get_selected_torrent(state.get_filtered_items())
                            if sel and "info_hash" in sel:
                                await _load_inspector_data(client, state, sel["info_hash"])
                    except asyncio.CancelledError:
                        break
                    except Exception:
                        pass

            poller_task = asyncio.create_task(poll_worker())
            background_tasks.add(poller_task)
            poller_task.add_done_callback(background_tasks.discard)

            with Live(
                console=console,
                refresh_per_second=10,
                transient=False,
                screen=fullscreen,
                auto_refresh=False,
            ) as live:
                while not effective_quit.is_set():
                    # Drain all available keys without blocking
                    while not key_queue.empty():
                        try:
                            k = key_queue.get_nowait()
                            await handle_key_input(k, client, state, effective_quit, background_tasks)
                        except asyncio.QueueEmpty:
                            break

                    state.check_status_expiration()
                    filtered_items = state.get_filtered_items()
                    renderable = build_dashboard_renderable(
                        filtered_items,
                        state.session_stats,
                        is_color=True,
                        height=console.height if fullscreen else None,
                        state=state,
                    )
                    live.update(renderable, refresh=True)

                    if once or effective_quit.is_set():
                        break

                    # Wait for next key event or timeout to refresh
                    try:
                        next_key = await asyncio.wait_for(key_queue.get(), timeout=0.08)
                        await handle_key_input(next_key, client, state, effective_quit, background_tasks)
                    except asyncio.TimeoutError:
                        pass

            poller_task.cancel()
            for t in list(background_tasks):
                t.cancel()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        _restore_all_terminals()
        if is_interactive:
            try:
                console.show_cursor(True)
            except Exception:
                pass
