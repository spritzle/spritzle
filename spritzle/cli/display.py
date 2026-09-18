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


def render_rich_table(
    console: Console,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    title: Optional[str] = None,
    box_style: box.Box = box.ROUNDED,
) -> None:
    """Render a modern table using Rich."""
    table = Table(
        title=title,
        box=box_style,
        header_style="bold cyan",
        show_header=bool(headers),
    )
    for h in headers:
        table.add_column(h)
    for r in rows:
        table.add_row(*[str(cell) for cell in r])
    console.print(table)


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
