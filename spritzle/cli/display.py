import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text


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


def format_speed(bps: Union[int, float], human: bool = True) -> str:
    """Format speed in bytes per second."""
    if not human:
        return str(bps)
    val = float(bps)
    for unit in ["B/s", "KB/s", "MB/s", "GB/s", "TB/s"]:
        if abs(val) < 1024.0:
            return f"{int(val)} {unit}" if unit == "B/s" else f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} PB/s"


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


def format_progress(val: Union[int, float], human: bool = True, width: int = 10) -> str:
    """Format progress ratio (0.0 - 1.0) with an inline bar."""
    if not human:
        return str(val)
    pct = max(0.0, min(1.0, float(val)))
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


def format_state(state: str, use_color: bool = True) -> str:
    """Format torrent state with semantic color coding."""
    if not use_color:
        return state
    color = STATE_COLORS.get(state.lower())
    if color:
        return f"[{color}]{state}[/{color}]"
    return state


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


def render_rich_table(
    console: Console,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    title: Optional[str] = None,
    box_style: box.Box = box.ROUNDED,
    caption: Optional[str] = None,
) -> None:
    """Render a modern table using Rich."""
    table = Table(
        title=title,
        caption=caption,
        caption_style="dim italic",
        box=box_style,
        header_style="bold cyan",
        show_header=bool(headers),
    )
    for h in headers:
        table.add_column(h)
    for r in rows:
        table.add_row(*[str(cell) for cell in r])
    console.print(table)


def render_post_add_card(
    console: Console,
    torrent: Dict[str, Any],
    color_opt: Optional[bool] = None,
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

    if state.lower() == "downloading" and peers == 0:
        status_text = "downloading (finding peers...)"
    elif state.lower() == "downloading" and peers > 0:
        status_text = f"downloading ({peers} peers)"
    else:
        status_text = state

    is_color = should_use_color(color_opt)
    display_name = name if name and name != info_hash else short_hash

    if is_color:
        console.print(
            f"[bold green]✔[/bold green] Added [bold]{escape(display_name)}[/bold] ([cyan]{escape(short_hash)}[/cyan])"
        )
        console.print(f"  [dim]Size:[/dim]      {size_str}")
        console.print(f"  [dim]Save Path:[/dim] {escape(save_path)}")
        if state.lower() == "downloading" and peers == 0:
            status_colored = "[green]downloading[/green] [yellow](finding peers...)[/yellow]"
        elif state.lower() == "downloading" and peers > 0:
            status_colored = f"[green]downloading[/green] ({peers} peers)"
        else:
            status_colored = format_state(state, use_color=True)
        console.print(f"  [dim]Status:[/dim]    {status_colored}")
        console.print("")
        console.print("Track progress:")
        console.print("  [cyan]spritzle list[/cyan]")
        lookup_ref = name if name and name != info_hash else info_hash
        console.print(f"  [cyan]spritzle info {escape(lookup_ref)}[/cyan]")
    else:
        print(f"Added {display_name} ({short_hash})")
        print(f"  Size:      {size_str}")
        print(f"  Save Path: {save_path}")
        print(f"  Status:    {status_text}")
        print("")
        print("Track progress:")
        print("  spritzle list")
        lookup_ref = name if name and name != info_hash else info_hash
        print(f"  spritzle info {lookup_ref}")


def render_kv_table(
    console: Console,
    items: Sequence[Tuple[str, Any]],
    title: Optional[str] = None,
    num_columns: Optional[int] = None,
    key_header: str = "Key",
    value_header: str = "Value",
    box_style: box.Box = box.ROUNDED,
    modified_keys: Optional[Set[str]] = None,
    caption: Optional[str] = None,
) -> None:
    """
    Render key-value items in a multi-column grid across terminal width
    to reduce vertical scrolling.
    """
    if not items:
        return

    mod_set = set(modified_keys) if modified_keys else set()
    if caption is None and mod_set:
        caption = "* modified from default"

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

    min_w = (len(title) + 6) if title else None
    table = Table(
        title=title,
        caption=caption,
        caption_style="dim italic",
        box=box_style,
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

