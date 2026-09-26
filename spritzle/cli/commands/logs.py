import asyncio
import sys
from typing import Any, Dict, List, Optional

import click
from rich.markup import escape
from rich.table import Table

from spritzle.cli.display import (
    get_border_style,
    get_box_style,
    get_console,
    get_response_error,
    print_error,
    print_json,
    should_use_color,
)


def parse_since_arg(val: Optional[str]) -> Optional[float]:
    """Parse a since argument into float seconds or unix timestamp."""
    if not val:
        return None
    v = val.strip().lower()
    if v.endswith("s"):
        try:
            return float(v[:-1])
        except ValueError:
            return None
    if v.endswith("m"):
        try:
            return float(v[:-1]) * 60
        except ValueError:
            return None
    if v.endswith("h"):
        try:
            return float(v[:-1]) * 3600
        except ValueError:
            return None
    if v.endswith("d"):
        try:
            return float(v[:-1]) * 86400
        except ValueError:
            return None
    try:
        return float(v)
    except ValueError:
        return None


LEVEL_STYLES = {
    "DEBUG": "dim cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "WARN": "yellow",
    "ERROR": "bold red",
    "CRITICAL": "bold white on red",
}


def render_plain_log_entry(entry: Dict[str, Any]) -> str:
    """Format a log entry for plain unstyled text output."""
    time_str = entry.get("time", "")
    lvl = entry.get("level", "INFO")
    module = entry.get("module", "")
    lineno = entry.get("lineno", 0)
    msg = entry.get("message", "")
    return f"[{lvl[:1]} {time_str} {module}:{lineno}] {msg}"


def render_styled_log_line(console, entry: Dict[str, Any]) -> None:
    """Print a single styled log entry for follow/streaming mode."""
    time_str = entry.get("time", "")
    if "T" in time_str:
        time_display = time_str.split("T")[1].rstrip("Z")
    else:
        time_display = time_str
    lvl = entry.get("level", "INFO").upper()
    style = LEVEL_STYLES.get(lvl, "none")
    module = entry.get("module", "")
    msg = escape(str(entry.get("message", "")))
    console.print(
        f"[dim]{time_display}[/dim] [{style}]{lvl:<7}[/{style}] [dim]{module}:[/dim] {msg}"
    )


@click.command("logs", short_help="View daemon logs.")
@click.option(
    "-n",
    "--lines",
    "--limit",
    "limit",
    type=int,
    default=50,
    show_default=True,
    help="Number of log entries to retrieve.",
)
@click.option(
    "-l",
    "--level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    default=None,
    help="Minimum log level filter.",
)
@click.option(
    "-q",
    "--query",
    "--regex",
    "regex",
    type=str,
    default=None,
    help="Filter log messages by regex pattern.",
)
@click.option(
    "-s",
    "--since",
    type=str,
    default=None,
    help="Show logs newer than relative duration (e.g. 60s, 10m, 1h) or unix timestamp.",
)
@click.option(
    "-f",
    "--follow",
    is_flag=True,
    default=False,
    help="Stream live log updates continuously.",
)
@click.option(
    "--clear",
    is_flag=True,
    default=False,
    help="Clear in-memory daemon log buffer.",
)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, limit, level, regex, since, follow, clear, json_output, plain):
    """View daemon logs."""
    client.do_command(
        f, limit, level, regex, since, follow, clear, json_output, plain
    )


async def f(
    client,
    limit: int = 50,
    level: Optional[str] = None,
    regex: Optional[str] = None,
    since: Optional[str] = None,
    follow: bool = False,
    clear: bool = False,
    json_output: bool = False,
    plain: bool = False,
):
    color_opt = getattr(client, "color", None)
    console = get_console(color_opt)
    use_color = should_use_color(color_opt) and not plain

    if clear:
        async with client.session.delete(client.url("log")) as resp:
            if resp.status != 200:
                print_error(
                    f"Failed to clear logs: {await get_response_error(resp)}",
                    color_opt=color_opt,
                )
                sys.exit(1)
            if json_output:
                print_json({"status": "cleared"})
            else:
                if use_color:
                    console.print("[green]Daemon log buffer cleared.[/green]")
                else:
                    print("Daemon log buffer cleared.")
            return

    params: Dict[str, Any] = {"limit": limit}
    if level:
        params["level"] = level.upper()
    if regex:
        params["regex"] = regex
    parsed_since = parse_since_arg(since)
    if parsed_since is not None:
        params["since"] = parsed_since

    async with client.session.get(client.url("log"), params=params) as resp:
        if resp.status != 200:
            print_error(
                f"Failed to retrieve logs: {await get_response_error(resp)}",
                color_opt=color_opt,
            )
            sys.exit(1)
        logs: List[Dict[str, Any]] = await resp.json()

    if json_output:
        print_json(logs)
        return

    last_ts: Optional[float] = None
    if logs:
        last_ts = logs[-1].get("timestamp")

    if not follow:
        if not logs:
            if not plain and use_color:
                console.print("[dim]No matching log entries found.[/dim]")
            else:
                print("No matching log entries found.")
            return

        if not use_color:
            for entry in logs:
                print(render_plain_log_entry(entry))
            return

        theme = client.cli_config.get("theme", "default")
        table = Table(
            box=get_box_style(theme),
            border_style=get_border_style(theme),
            caption_style="none",
            show_header=True,
            header_style="bold #b55dc4",
        )
        table.add_column("Time", style="dim", no_wrap=True)
        table.add_column("Level", no_wrap=True)
        table.add_column("Module", style="dim", no_wrap=True)
        table.add_column("Message")

        for entry in logs:
            time_str = entry.get("time", "")
            if "T" in time_str:
                time_display = time_str.split("T")[1].rstrip("Z")
            else:
                time_display = time_str
            lvl = entry.get("level", "INFO").upper()
            style = LEVEL_STYLES.get(lvl, "none")
            module = f"{entry.get('module', '')}:{entry.get('lineno', '')}"
            msg = escape(str(entry.get("message", "")))
            table.add_row(
                time_display,
                f"[{style}]{lvl}[/{style}]",
                module,
                msg,
            )
        console.print(table)
        return

    # Follow mode
    for entry in logs:
        if not use_color:
            print(render_plain_log_entry(entry))
        else:
            render_styled_log_line(console, entry)

    try:
        while True:
            await asyncio.sleep(1.0)
            poll_params = dict(params)
            if last_ts is not None:
                poll_params["since"] = last_ts + 0.000001
            poll_params["limit"] = 100
            async with client.session.get(
                client.url("log"), params=poll_params
            ) as resp:
                if resp.status == 200:
                    new_logs = await resp.json()
                    for entry in new_logs:
                        if not use_color:
                            print(render_plain_log_entry(entry))
                        else:
                            render_styled_log_line(console, entry)
                        last_ts = entry.get("timestamp", last_ts)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
