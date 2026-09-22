import datetime
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def get_box_style(theme: Optional[str] = None) -> box.Box:
    """Return appropriate Rich box style based on active theme."""
    if theme == "minimal":
        return box.HORIZONTALS
    elif theme == "ascii":
        return box.ASCII
    return box.ROUNDED


def get_border_style(theme: Optional[str] = None) -> str:
    """Return table border style based on active theme."""
    if theme == "ascii":
        return "none"
    return "dim"


def should_use_color(color_opt: Optional[bool] = None) -> bool:
    """Determine whether color and rich terminal styling should be used."""
    if color_opt is not None:
        return color_opt
    if os.getenv("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def get_console(color_opt: Optional[bool] = None, stderr: bool = False) -> Console:
    """Get a Rich Console configured for interactive or non-interactive use."""
    use_color = should_use_color(color_opt)
    target_file = sys.stderr if stderr else sys.stdout
    return Console(
        file=target_file,
        no_color=not use_color,
        force_terminal=use_color,
        highlight=False,
    )


def format_speed(
    bps: Union[int, float],
    human: bool = True,
    use_color: bool = False,
    is_upload: bool = False,
) -> str:
    """Format speed in bytes per second."""
    if not human:
        return str(bps)
    val = float(bps)
    formatted = "0 B/s"
    for unit in ["B/s", "KB/s", "MB/s", "GB/s", "TB/s"]:
        if abs(val) < 1024.0:
            formatted = f"{int(val)} {unit}" if unit == "B/s" else f"{val:.1f} {unit}"
            break
        val /= 1024.0
    else:
        formatted = f"{val:.1f} PB/s"

    if not use_color:
        return formatted

    if val <= 0:
        return f"[dim]{formatted}[/dim]"

    if is_upload:
        return f"[blue]▲ {formatted}[/blue]"
    return f"[green]▼ {formatted}[/green]"


def format_bytes(b: Union[int, float], human: bool = True) -> str:
    """Format byte size to human readable units."""
    if not human:
        return str(b)
    val = float(b)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(val) < 1024.0:
            return f"{int(val)} {unit}" if unit == "B" else f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} PB"


def format_progress(
    val: Union[int, float],
    human: bool = True,
    width: int = 10,
    style: str = "blocks",
    use_color: bool = False,
) -> str:
    """Format progress ratio (0.0 - 1.0) with an inline bar."""
    if not human:
        return str(val)
    pct = max(0.0, min(1.0, float(val)))
    if style == "smooth":
        filled = int(round(pct * width))
        unfilled = width - filled
        pct_str = f"{pct * 100:.1f}%"
        if use_color:
            if pct >= 1.0:
                bar = f"[blue]{'━' * filled}[/blue]"
            elif filled > 0:
                bar = f"[green]{'━' * filled}[/green][bright_black]{'━' * unfilled}[/bright_black]"
            else:
                bar = f"[bright_black]{'━' * width}[/bright_black]"
            return f"{bar}  [bold]{pct_str}[/bold]"
        else:
            bar = "━" * filled + "─" * unfilled
            return f"{bar}  {pct_str}"
    else:
        filled = int(round(pct * width))
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {pct * 100:.1f}%"


STATE_COLORS: Dict[str, str] = {
    "downloading": "green",
    "seeding": "blue",
    "checking": "magenta",
    "checking_files": "magenta",
    "checking_resume_data": "magenta",
    "queued": "yellow",
    "queued_for_checking": "yellow",
    "paused": "dim",
    "error": "red",
}

STATE_GLYPHS: Dict[str, str] = {
    "downloading": "●",
    "seeding": "●",
    "checking": "●",
    "checking_files": "●",
    "checking_resume_data": "●",
    "queued": "●",
    "queued_for_checking": "●",
    "paused": "⏸",
    "error": "✖",
}


def format_state(state: str, use_color: bool = True) -> str:
    """Format torrent state with semantic color coding."""
    if not use_color:
        return state
    color = STATE_COLORS.get(state.lower())
    if color:
        return f"[{color}]{state}[/{color}]"
    return state


def format_state_pill(
    state: str,
    use_color: bool = True,
    peers: Optional[int] = None,
) -> str:
    """Format torrent state as a modern status pill with glyph."""
    st = state.lower()
    color = STATE_COLORS.get(st, "white")
    glyph = STATE_GLYPHS.get(st, "●")

    if st == "downloading" and peers == 0:
        if use_color:
            return "[green]● downloading[/green] [yellow](finding peers...)[/yellow]"
        return "● downloading (finding peers...)"
    elif st == "downloading" and peers is not None and peers > 0:
        if use_color:
            return f"[green]● downloading[/green] [dim]({peers} peers)[/dim]"
        return f"● downloading ({peers} peers)"

    if not use_color:
        return f"{glyph} {state}"

    if st == "error":
        return f"[bold red]{glyph} {state}[/bold red]"
    elif st == "paused":
        return f"[dim]{glyph} {state}[/dim]"
    else:
        return f"[{color}]{glyph} {state}[/{color}]"


def format_latency(ms: Union[int, float, None], use_color: bool = True) -> str:
    """Format ping latency with color-coded tier."""
    if ms is None:
        return "[dim]-[/dim]" if use_color else "-"
    val = float(ms)
    s = f"{val:.1f} ms"
    if not use_color:
        return s
    if val < 50.0:
        return f"[green]● {s}[/green]"
    elif val < 150.0:
        return f"[yellow]● {s}[/yellow]"
    return f"[red]● {s}[/red]"


def format_bool(val: bool, human: bool = True, use_color: bool = True) -> str:
    """Format boolean values, optionally as badges."""
    if not human:
        return str(val)
    if not use_color:
        return "True" if val else "False"
    if val:
        return f"[bold green]{escape('[on]')}[/bold green]"
    return f"[dim]{escape('[off]')}[/dim]"


def format_eta(seconds: Union[int, float, None], human: bool = True) -> str:
    """Format ETA in seconds to human readable string."""
    if seconds is None or seconds < 0 or seconds == float("inf"):
        return "--" if human else "-1"
    if not human:
        return str(int(seconds))
    sec = int(round(seconds))
    if sec == 0:
        return "0s"
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        m, s = divmod(sec, 60)
        return f"{m}m {s:02d}s"
    if sec < 86400:
        h, rem = divmod(sec, 3600)
        m, _ = divmod(rem, 60)
        return f"{h}h {m:02d}m"
    d, rem = divmod(sec, 86400)
    h, _ = divmod(rem, 3600)
    return f"{d}d {h:02d}h"


def format_datetime(ts: Union[int, float, None], human: bool = True) -> str:
    """Format unix timestamp into local human-readable datetime string."""
    if ts is None:
        return "--" if human else "0"
    try:
        val = float(ts)
        if val <= 0:
            return "--" if human else "0"
        if not human:
            return str(int(val))
        dt = datetime.datetime.fromtimestamp(val).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def render_rich_table(
    console: Console,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    title: Optional[str] = None,
    box_style: Optional[box.Box] = None,
    border_style: Optional[str] = "dim",
    caption: Optional[str] = None,
    column_styles: Optional[Dict[str, Dict[str, Any]]] = None,
    theme: Optional[str] = None,
) -> None:
    """Render a modern table using Rich."""
    resolved_box = box_style if box_style is not None else get_box_style(theme)
    resolved_border = border_style if border_style is not None else get_border_style(theme)
    table = Table(
        title=title,
        title_style="bold",
        caption=caption,
        caption_style="none",
        box=resolved_box,
        border_style=resolved_border,
        header_style="bold cyan",
        show_header=bool(headers),
        pad_edge=True,
    )
    for h in headers:
        kw = (column_styles or {}).get(h, {})
        table.add_column(h, **kw)
    for r in rows:
        table.add_row(*[str(cell) for cell in r])
    console.print(table)


def render_post_add_card(
    console: Console,
    torrent: Dict[str, Any],
    color_opt: Optional[bool] = None,
    theme: Optional[str] = None,
) -> None:
    """Render informative summary card after adding a torrent."""
    name = torrent.get("name") or torrent.get("info_hash", "torrent")
    info_hash = torrent.get("info_hash", "")
    short_hash = f"{info_hash[:8]}..." if len(info_hash) >= 8 else info_hash
    size_bytes = torrent.get("size") or torrent.get("total_wanted") or torrent.get("total_size") or 0
    size_str = format_bytes(size_bytes) if size_bytes > 0 else "unknown (fetching metadata...)"
    save_path = torrent.get("save_path", "")
    state = torrent.get("state", "downloading")
    peers = torrent.get("num_peers", 0)

    is_color = should_use_color(color_opt)
    display_name = name if name and name != info_hash else short_hash

    if is_color:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim", no_wrap=True, width=12)
        grid.add_column()

        status_pill = format_state_pill(state, use_color=True, peers=peers)
        grid.add_row("Status", status_pill)
        grid.add_row("Size", size_str)
        grid.add_row("Save Path", escape(save_path))
        lookup_ref = name if name and name != info_hash else info_hash
        grid.add_row("", "")
        grid.add_row("[bold cyan]Track progress[/bold cyan]", "")
        grid.add_row("  List all", "[cyan]spritzle list[/cyan]")
        grid.add_row("  Details", f"[cyan]spritzle info {escape(lookup_ref)}[/cyan]")

        box_style = get_box_style(theme)
        border_style = get_border_style(theme)
        panel = Panel(
            grid,
            title=f"[bold green]✔[/bold green] Added [bold]{escape(display_name)}[/bold] ([cyan]{escape(short_hash)}[/cyan])",
            border_style=border_style,
            box=box_style,
            padding=(1, 2),
        )
        console.print(panel)
    else:
        print(f"Added {display_name} ({short_hash})")
        print(f"  Size:      {size_str}")
        print(f"  Save Path: {save_path}")
        print(f"  Status:    {state}")
        print("")
        print("Track progress:")
        print("  spritzle list")
        lookup_ref = name if name and name != info_hash else info_hash
        print(f"  spritzle info {lookup_ref}")


def render_info_card(
    console: Console,
    data: Dict[str, Any],
    info_hash: str,
    color_opt: Optional[bool] = None,
    theme: Optional[str] = None,
) -> None:
    """Render comprehensive torrent information in a modern multi-section card."""
    is_color = should_use_color(color_opt)
    name = data.get("name", "<unknown>")
    state = str(data.get("state", "unknown"))
    progress = float(data.get("progress", 0.0))
    dl_rate = float(data.get("download_rate", 0))
    ul_rate = float(data.get("upload_rate", 0))
    total_size = float(data.get("total_size", 0))
    total_done = float(data.get("total_done", 0))
    total_wanted = float(data.get("total_wanted", 0))
    num_peers = int(data.get("num_peers", 0))
    num_seeds = int(data.get("num_seeds", 0))
    num_pieces = data.get("num_pieces", 0)
    save_path = data.get("save_path", "")
    tags = data.get("spritzle.tags", [])
    tags_str = ", ".join(tags) if isinstance(tags, list) and tags else (str(tags) if tags else "<none>")

    size_target = total_wanted if total_wanted > 0 else total_size
    eta_sec = (size_target - total_done) / dl_rate if dl_rate > 0 and size_target > total_done else None

    # Error checking: only show if real error
    err_str = None
    if data.get("last_error"):
        err_str = str(data["last_error"])
    elif data.get("error"):
        err_val = data["error"]
        if isinstance(err_val, dict) and err_val.get("value", 0) != 0:
            err_str = err_val.get("message") or str(err_val)
        elif err_val and not isinstance(err_val, dict):
            err_str = str(err_val)
    elif data.get("errc"):
        errc = data["errc"]
        if isinstance(errc, dict) and errc.get("value", 0) != 0:
            err_str = errc.get("message") or str(errc)
        elif isinstance(errc, int) and errc != 0:
            err_str = str(errc)

    state_pill = format_state_pill(state, use_color=is_color, peers=num_peers)
    prog_disp = format_progress(
        progress, human=True, width=16, style="smooth" if is_color else "blocks", use_color=is_color
    )
    size_disp = (
        f"{format_bytes(total_done)} / {format_bytes(size_target)}"
        if size_target > 0
        else format_bytes(total_done)
    )
    eta_disp = format_eta(eta_sec)

    added_time = data.get("added_time")
    added_str = format_datetime(added_time)
    completed_time = data.get("completed_time")
    completed_str = (
        format_datetime(completed_time)
        if completed_time and float(completed_time) > 0
        else None
    )

    total_up = float(data.get("all_time_upload") or data.get("total_upload") or 0)
    total_dl = float(data.get("all_time_download") or data.get("total_done") or data.get("total_download") or 0)
    ratio = (total_up / total_dl) if total_dl > 0 else 0.0
    if is_color:
        ratio_str = f"[bold green]{ratio:.2f}[/bold green]" if ratio >= 1.0 else f"[yellow]{ratio:.2f}[/yellow]"
    else:
        ratio_str = f"{ratio:.2f}"

    total_pieces = data.get("total_pieces")
    piece_length = data.get("piece_length")
    if total_pieces:
        pieces_disp = f"{num_pieces} / {total_pieces}"
        if piece_length:
            pieces_disp += f" ({format_bytes(piece_length)})"
    else:
        pieces_disp = str(num_pieces)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True, width=14)
    grid.add_column()

    grid.add_row("State", state_pill)
    grid.add_row("Info Hash", f"[cyan]{info_hash}[/cyan]" if is_color else info_hash)
    if added_str != "--":
        grid.add_row("Added", added_str)
    if completed_str:
        grid.add_row("Completed", completed_str)
    if tags_str != "<none>":
        grid.add_row("Tags", f"[magenta]{escape(tags_str)}[/magenta]" if is_color else tags_str)

    grid.add_row("", "")
    grid.add_row("[bold cyan]Transfer[/bold cyan]", "")
    grid.add_row(
        "  Progress",
        f"{prog_disp}  [dim]({size_disp})[/dim]" if is_color else f"{prog_disp} ({size_disp})",
    )
    dl_disp = format_speed(dl_rate, use_color=is_color)
    ul_disp = format_speed(ul_rate, use_color=is_color, is_upload=True)
    grid.add_row(
        "  Speed",
        f"{dl_disp}   {ul_disp}   [dim]ETA:[/dim] {eta_disp}"
        if is_color
        else f"DL: {dl_disp}  UL: {ul_disp}  ETA: {eta_disp}",
    )
    grid.add_row("  Share Ratio", ratio_str)

    grid.add_row("", "")
    grid.add_row("[bold cyan]Swarm[/bold cyan]", "")
    grid.add_row(
        "  Peers",
        f"{num_peers} connected [dim](seeds: {num_seeds})[/dim]"
        if is_color
        else f"{num_peers} connected (seeds: {num_seeds})",
    )
    grid.add_row("  Pieces", pieces_disp)

    grid.add_row("", "")
    grid.add_row("[bold cyan]Storage[/bold cyan]", "")
    grid.add_row("  Save Path", escape(save_path))

    if err_str:
        grid.add_row("", "")
        grid.add_row("[bold red]Error[/bold red]", f"[red]{escape(err_str)}[/red]" if is_color else err_str)

    title = f"[bold]Torrent Info: [bold white]{escape(name)}[/bold white][/bold]" if is_color else f"Torrent Info: {name}"
    box_style = get_box_style(theme)
    border_style = get_border_style(theme)
    panel = Panel(grid, title=title, border_style=border_style, box=box_style, padding=(1, 2))
    console.print(panel)

    # Trackers Section
    trackers = data.get("trackers") or []
    if trackers:
        tracker_table = Table(
            title="Trackers",
            title_style="bold",
            caption_style="none",
            box=box_style,
            border_style=border_style,
            header_style="bold cyan",
            show_header=True,
            pad_edge=True,
        )
        tracker_table.add_column("Tier", justify="right", width=6, style="dim")
        tracker_table.add_column("URL", style="white")
        tracker_table.add_column("Status", no_wrap=True)

        for tr in trackers:
            tier_str = str(tr.get("tier", 0))
            url_str = escape(str(tr.get("url", "")))
            if tr.get("updating"):
                st_disp = "[yellow]updating[/yellow]" if is_color else "updating"
            elif tr.get("fails", 0) > 0 or (tr.get("last_error") and tr["last_error"].get("value", 0) != 0):
                msg = tr.get("message") or (tr.get("last_error") or {}).get("message") or f"error ({tr.get('fails')} fails)"
                st_disp = f"[red]{escape(str(msg))}[/red]" if is_color else str(msg)
            elif tr.get("verified") or tr.get("is_working"):
                st_disp = "[green]working[/green]" if is_color else "working"
            else:
                st_disp = "[dim]idle[/dim]" if is_color else "idle"

            tracker_table.add_row(tier_str, url_str, st_disp)
        console.print(tracker_table)

    # Connected Peers Section
    peers = data.get("peers") or []
    if peers:
        peer_table = Table(
            title=f"Connected Peers ({len(peers)})",
            title_style="bold",
            caption_style="none",
            box=box_style,
            border_style=border_style,
            header_style="bold cyan",
            show_header=True,
            pad_edge=True,
        )
        peer_table.add_column("IP Address", style="cyan", no_wrap=True)
        peer_table.add_column("Client", style="dim", no_wrap=True)
        peer_table.add_column("Down Speed", justify="right", no_wrap=True)
        peer_table.add_column("Up Speed", justify="right", no_wrap=True)
        peer_table.add_column("Progress", min_width=18, no_wrap=True)

        display_peers = peers[:10]
        for p in display_peers:
            ip_str = escape(str(p.get("ip", "")))
            client_val = str(p.get("client") or "").strip()
            client_str = escape(client_val) if client_val else "[dim]<unknown>[/dim]"
            p_down = format_speed(p.get("down_speed", 0), use_color=is_color)
            p_up = format_speed(p.get("up_speed", 0), use_color=is_color, is_upload=True)
            p_prog = format_progress(
                p.get("progress", 0.0),
                human=True,
                width=10,
                style="smooth" if is_color else "blocks",
                use_color=is_color,
            )
            peer_table.add_row(ip_str, client_str, p_down, p_up, p_prog)

        if len(peers) > 10:
            peer_table.caption = (
                f"[dim]... and {len(peers) - 10} more peers (use --json to see all)[/dim]"
                if is_color
                else f"... and {len(peers) - 10} more peers (use --json to see all)"
            )
        console.print(peer_table)

    # Files Section
    files = data.get("files") or []
    if files:
        file_table = Table(
            title=f"Files ({len(files)})",
            title_style="bold",
            caption_style="none",
            box=box_style,
            border_style=border_style,
            header_style="bold cyan",
            show_header=True,
            pad_edge=True,
        )
        file_table.add_column("#", justify="right", style="dim", width=4)
        file_table.add_column("Path", style="white")
        file_table.add_column("Size", justify="right", no_wrap=True)
        file_table.add_column("Progress", min_width=18, no_wrap=True)

        display_files = files[:15]
        for f in display_files:
            idx_str = str(f.get("index", 0))
            path_str = escape(str(f.get("path", "")))
            sz_str = format_bytes(f.get("size", 0))
            f_prog = format_progress(
                f.get("progress", 0.0),
                human=True,
                width=10,
                style="smooth" if is_color else "blocks",
                use_color=is_color,
            )
            file_table.add_row(idx_str, path_str, sz_str, f_prog)

        if len(files) > 15:
            file_table.caption = (
                f"[dim]... and {len(files) - 15} more files (use --json to see all)[/dim]"
                if is_color
                else f"... and {len(files) - 15} more files (use --json to see all)"
            )
        console.print(file_table)


def render_status_card(
    console: Console,
    remote_name: str,
    url: str,
    daemon_id: str,
    version: str,
    latency_ms: Optional[float],
    uptime_str: str,
    num_torrents: int,
    color_opt: Optional[bool] = None,
    theme: Optional[str] = None,
) -> None:
    """Render daemon health and connectivity in a modern hero status card."""
    is_color = should_use_color(color_opt)
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="dim", no_wrap=True, width=12)
    grid.add_column()

    status_pill = "[bold green]● online[/bold green]" if is_color else "● online"
    latency_pill = format_latency(latency_ms, use_color=is_color)

    grid.add_row(
        "Remote",
        f"[bold cyan]{escape(remote_name)}[/bold cyan]  {status_pill}  {latency_pill}"
        if is_color
        else f"{remote_name}  online  {latency_ms} ms",
    )
    grid.add_row("URL", escape(url))
    grid.add_row("Daemon ID", f"[dim]{escape(daemon_id)}[/dim]" if is_color else daemon_id)
    grid.add_row("Version", escape(version))
    grid.add_row("Uptime", uptime_str)
    grid.add_row(
        "Torrents",
        f"[bold]{num_torrents}[/bold] active" if is_color else f"{num_torrents} active",
    )

    box_style = get_box_style(theme)
    border_style = get_border_style(theme)
    panel = Panel(
        grid,
        title="[bold]Spritzle Daemon Status[/bold]" if is_color else "Spritzle Daemon Status",
        border_style=border_style,
        box=box_style,
        padding=(1, 2),
    )
    console.print(panel)


def render_stats_cards(
    console: Console,
    summary_data: Dict[str, Any],
    color_opt: Optional[bool] = None,
    theme: Optional[str] = None,
) -> None:
    """Render session statistics in an organized, multi-section dashboard panel."""
    is_color = should_use_color(color_opt)
    ratio = float(summary_data["transfer"]["ratio"])
    if is_color:
        ratio_pill = (
            f"[bold green]{ratio:.2f}[/bold green]"
            if ratio >= 1.0
            else f"[bold yellow]{ratio:.2f}[/bold yellow]"
        )
    else:
        ratio_pill = f"{ratio:.2f}"

    dht_nodes = int(summary_data["dht"]["nodes"])
    if dht_nodes < 10:
        dht_status = (
            f"[yellow]●[/yellow] {dht_nodes} (bootstrapping DHT...)"
            if is_color
            else f"{dht_nodes} (bootstrapping DHT...)"
        )
    else:
        dht_status = f"[magenta]● {dht_nodes} nodes[/magenta]" if is_color else f"{dht_nodes} nodes"

    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(ratio=1)
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(ratio=1)

    # Torrents & Transfer Section
    grid.add_row("[bold cyan]Torrents[/bold cyan]", "", "[bold cyan]Transfer & Bandwidth[/bold cyan]", "")
    grid.add_row(
        "  Downloading", str(summary_data["torrents"]["downloading"]),
        "  Downloaded", str(summary_data["transfer"]["downloaded"]),
    )
    grid.add_row(
        "  Seeding", str(summary_data["torrents"]["seeding"]),
        "  Uploaded", str(summary_data["transfer"]["uploaded"]),
    )
    grid.add_row(
        "  Checking", str(summary_data["torrents"]["checking"]),
        "  Total In / Out", f"{summary_data['transfer']['total_received']} / {summary_data['transfer']['total_sent']}",
    )
    grid.add_row(
        "  Stopped", str(summary_data["torrents"]["stopped"]),
        "  Share Ratio", ratio_pill,
    )
    grid.add_row(
        "  Queued (DL/Seed)", f"{summary_data['torrents']['queued_download']} / {summary_data['torrents']['queued_seed']}",
        "  Wasted Data", str(summary_data["transfer"]["wasted"]),
    )

    grid.add_row("", "", "", "")
    grid.add_row("[bold cyan]Swarm & Network[/bold cyan]", "", "[bold cyan]DHT Status[/bold cyan]", "")
    grid.add_row(
        "  Connected Peers", str(summary_data["peers"]["connected"]),
        "  Status", dht_status,
    )
    grid.add_row(
        "  Half-Open Peers", str(summary_data["peers"]["half_open"]),
        "  DHT Torrents", str(summary_data["dht"]["torrents"]),
    )
    grid.add_row(
        "  Conn Attempts", str(summary_data["peers"]["connection_attempts"]),
        "", "",
    )
    grid.add_row(
        "  Incoming Conn", str(summary_data["peers"]["incoming_connections"]),
        "", "",
    )

    box_style = get_box_style(theme)
    border_style = get_border_style(theme)
    panel = Panel(
        grid,
        title="[bold]Session Statistics Summary[/bold]" if is_color else "Session Statistics Summary",
        subtitle="[dim]Run 'spritzle stats --all' for raw internal counters[/dim]"
        if is_color
        else "Run 'spritzle stats --all' for raw internal counters",
        border_style=border_style,
        box=box_style,
        padding=(1, 2),
    )
    console.print(panel)


def render_empty_list_card(
    console: Console,
    dht_nodes: Optional[int] = None,
    query: Optional[Sequence[str]] = None,
    color_opt: Optional[bool] = None,
    theme: Optional[str] = None,
) -> None:
    """Render a clean onboarding card when list is empty."""
    is_color = should_use_color(color_opt)
    if query:
        console.print(
            "[yellow]No torrents match the specified filter.[/yellow]"
            if is_color
            else "No torrents match the specified filter."
        )
        return

    grid = Table.grid(padding=(0, 2))
    grid.add_column()

    grid.add_row("[bold]No torrents in session.[/bold]" if is_color else "No torrents in session.")
    grid.add_row("")
    grid.add_row("To add a torrent, run:")
    grid.add_row(
        "  [cyan]spritzle add <path | url | magnet | info-hash>[/cyan]"
        if is_color
        else "  spritzle add <path | url | magnet | info-hash>"
    )
    grid.add_row("")
    grid.add_row("Examples:")
    grid.add_row(
        "  [green]$[/green] spritzle add archlinux-x86_64.iso.torrent"
        if is_color
        else "  $ spritzle add archlinux-x86_64.iso.torrent"
    )
    grid.add_row(
        "  [green]$[/green] spritzle add 'magnet:?xt=urn:btih:...'"
        if is_color
        else "  $ spritzle add 'magnet:?xt=urn:btih:...'"
    )

    if dht_nodes is not None and dht_nodes < 10:
        grid.add_row("")
        grid.add_row("[yellow]●[/yellow] bootstrapping DHT..." if is_color else "bootstrapping DHT...")

    box_style = get_box_style(theme)
    border_style = get_border_style(theme)
    panel = Panel(
        grid,
        title="[bold]Spritzle Session[/bold]" if is_color else "Spritzle Session",
        border_style=border_style,
        box=box_style,
        padding=(1, 2),
    )
    console.print(panel)


def render_kv_table(
    console: Console,
    items: Sequence[Tuple[str, Any]],
    title: Optional[str] = None,
    num_columns: Optional[int] = None,
    key_header: str = "Key",
    value_header: str = "Value",
    box_style: Optional[box.Box] = None,
    border_style: Optional[str] = "dim",
    modified_keys: Optional[Set[str]] = None,
    caption: Optional[str] = None,
    theme: Optional[str] = None,
) -> None:
    """
    Render key-value items in a multi-column grid across terminal width
    to reduce vertical scrolling.
    """
    if not items:
        return

    mod_set = set(modified_keys) if modified_keys else set()
    is_color = not console.no_color
    if caption is None and mod_set:
        caption = "[yellow]*[/yellow] modified from default" if is_color else "* modified from default"

    num_items = len(items)
    if num_columns is None:
        width = console.width
        if num_items <= 8:
            num_columns = 1
        elif width >= 140:
            num_columns = 3
        elif width >= 80:
            num_columns = 2
        else:
            num_columns = 1

    num_columns = max(1, min(num_columns, num_items))
    rows_per_col = (num_items + num_columns - 1) // num_columns

    resolved_box = box_style if box_style is not None else get_box_style(theme)
    resolved_border = border_style if border_style is not None else get_border_style(theme)

    min_w = (len(title) + 6) if title else None
    table = Table(
        title=title,
        title_style="bold",
        caption=caption,
        caption_style="none",
        box=resolved_box,
        border_style=resolved_border,
        header_style="bold cyan",
        show_header=True,
        min_width=min_w,
    )

    for _ in range(num_columns):
        table.add_column(key_header, style="cyan", no_wrap=True)
        table.add_column(value_header, no_wrap=(num_columns > 1))

    for r in range(rows_per_col):
        row_cells: List[Union[str, Text]] = []
        for c in range(num_columns):
            idx = c * rows_per_col + r
            if idx < num_items:
                k, v = items[idx]
                is_modified = k in mod_set
                if is_modified:
                    k_str = f"[bold yellow]* {escape(str(k))}[/bold yellow]"
                else:
                    k_str = escape(str(k))

                if isinstance(v, Text):
                    v_cell: Union[str, Text] = v
                elif isinstance(v, bool):
                    v_cell = format_bool(v, human=True, use_color=True)
                    if is_modified:
                        v_cell = f"[bold yellow]{v_cell}[/bold yellow]"
                elif v == "":
                    v_cell = '[bold yellow]""[/bold yellow]' if is_modified else '[dim]""[/dim]'
                elif v is None:
                    v_cell = "[bold yellow]None[/bold yellow]" if is_modified else "[dim]None[/dim]"
                else:
                    v_cell = (
                        f"[bold yellow]{escape(str(v))}[/bold yellow]"
                        if is_modified
                        else escape(str(v))
                    )
                row_cells.extend([k_str, v_cell])
            else:
                row_cells.extend(["", ""])
        table.add_row(*row_cells)

    console.print(table)



def render_plain_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    header: bool = True,
    delimiter: str = "\t",
) -> None:
    """Render a plain delimited table for scripts, pipes, and hooks."""
    if header and headers:
        print(delimiter.join(str(h) for h in headers))
    for r in rows:
        print(delimiter.join(str(cell) for cell in r))


def print_json(data: Any) -> None:
    """Print structured JSON output."""
    print(json.dumps(data, indent=2))


def print_success(msg: str, color_opt: Optional[bool] = None) -> None:
    """Print a success message with green glyph in TTY."""
    console = get_console(color_opt)
    if should_use_color(color_opt):
        console.print(f"[bold green]✔[/bold green] {msg}")
    else:
        print(msg)


def print_error(msg: str, color_opt: Optional[bool] = None) -> None:
    """Print an error message to stderr with red glyph in TTY."""
    console = get_console(color_opt, stderr=True)
    if should_use_color(color_opt):
        console.print(f"[bold red]✖[/bold red] [red]{msg}[/red]")
    else:
        print(f"Error: {msg}", file=sys.stderr)


def print_warning(msg: str, color_opt: Optional[bool] = None) -> None:
    """Print a warning message to stderr."""
    console = get_console(color_opt, stderr=True)
    if should_use_color(color_opt):
        console.print(f"[bold yellow]⚠[/bold yellow] {msg}")
    else:
        print(f"Warning: {msg}", file=sys.stderr)


async def get_response_error(resp: Any) -> str:
    """Extract descriptive error message from daemon response."""
    msg = getattr(resp, "reason", None) or f"HTTP {getattr(resp, 'status', 500)}"
    if hasattr(resp, "json"):
        try:
            data = await resp.json()
            if isinstance(data, dict):
                msg = data.get("message") or data.get("reason") or msg
        except Exception:
            if hasattr(resp, "text"):
                try:
                    text = await resp.text()
                    if text:
                        msg = text.strip()
                except Exception:
                    pass
    return str(msg).strip().rstrip("\r\n")

