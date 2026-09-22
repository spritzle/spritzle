import asyncio
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

try:
    import termios
    import tty
except ImportError:
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]

from rich.console import Group
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from spritzle.cli.display import (
    format_bytes,
    format_eta,
    format_progress,
    format_speed,
    format_state_pill,
    get_console,
    get_display_state,
    should_use_color,
)


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

    dash_keys = "name,info_hash,state,progress,download_rate,upload_rate,total_wanted,total_done,num_peers,num_seeds,paused,flags,errc,last_error"
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

    title = f"[bold]{escape(name)}[/bold] ([cyan]{escape(short_hash)}[/cyan])" if is_color else f"{name} ({short_hash})"
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


def build_dashboard_renderable(
    items: List[Dict[str, Any]],
    stats: Dict[str, Any],
    is_color: bool = True,
    height: Optional[int] = None,
) -> Any:
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

    table = Table(
        box=None if not is_color else Table.grid().box,
        header_style="bold cyan",
        show_header=True,
        expand=True,
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
            state = get_display_state(t)
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

            status_str = format_state_pill(state, use_color=is_color)

            table.add_row(
                escape(str(name)),
                status_str,
                format_progress(
                    progress, human=True, width=10, style="smooth" if is_color else "blocks", use_color=is_color
                ),
                format_bytes(total_wanted),
                format_speed(dl_rate, use_color=is_color),
                format_speed(ul_rate, use_color=is_color, is_upload=True),
                f"{num_peers} ({num_seeds})",
                format_eta(eta_sec),
            )

    panel = Panel(
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
    return panel


class KeyPressWatcher:
    """Async context manager that puts stdin in cbreak mode to detect 'q' keypress."""

    def __init__(
        self,
        quit_event: Optional[asyncio.Event] = None,
        fd: Optional[int] = None,
    ) -> None:
        self.quit_event = quit_event if quit_event is not None else asyncio.Event()
        self._target_fd = fd
        self._fd: Optional[int] = None
        self._old_settings: Optional[Any] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

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
                self._loop = asyncio.get_running_loop()
                self._loop.add_reader(self._fd, self._on_stdin)
        except Exception:
            self._cleanup()
        return self

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
        if b"q" in data or b"Q" in data or b"\x03" in data:
            self.quit_event.set()

    def _cleanup(self) -> None:
        if self._loop and self._fd is not None:
            try:
                self._loop.remove_reader(self._fd)
            except Exception:
                pass
        if self._fd is not None and self._old_settings is not None and termios is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass
        self._fd = None
        self._old_settings = None
        self._loop = None

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._cleanup()


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

    try:
        async with KeyPressWatcher(quit_event=quit_event) as watcher:
            if is_interactive:
                with Live(
                    console=console,
                    refresh_per_second=4,
                    transient=False,
                    screen=fullscreen,
                ) as live:
                    while True:
                        items = await fetch_torrents_with_status(client, query)
                        stats = await fetch_session_stats(client)
                        render_height = console.height if fullscreen else None
                        live.update(
                            build_dashboard_renderable(
                                items, stats, is_color=True, height=render_height
                            )
                        )

                        if once:
                            break
                        if await _sleep_or_quit(interval, watcher.quit_event):
                            break
            else:
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
                    if await _sleep_or_quit(interval, watcher.quit_event):
                        break
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass


