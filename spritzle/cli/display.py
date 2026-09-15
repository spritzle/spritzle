import json
import os
import sys
from typing import Any, Dict, Optional, Sequence, Union

from rich import box
from rich.console import Console
from rich.table import Table


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
        return "[bold green][on][/bold green]"
    return "[dim][off][/dim]"


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
