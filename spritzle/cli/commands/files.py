import sys
from typing import Dict

import click
from rich.table import Table
from tabulate import tabulate

from spritzle.cli.completion_helpers import complete_torrent_identifiers
from spritzle.cli.display import (
    HEADER_STYLE,
    format_bytes,
    get_border_style,
    get_box_style,
    get_console,
    get_response_error,
    print_error,
    print_json,
    print_success,
    should_use_color,
)
from spritzle.cli.lookup import resolve_single_torrent

PRIORITY_ALIASES: Dict[str, int] = {
    "0": 0,
    "skip": 0,
    "dont_download": 0,
    "off": 0,
    "none": 0,
    "1": 1,
    "low": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "normal": 4,
    "default": 4,
    "5": 5,
    "6": 6,
    "high": 6,
    "7": 7,
    "top": 7,
    "max": 7,
}

PRIORITY_NAMES: Dict[int, str] = {
    0: "0 (skip)",
    1: "1 (low)",
    2: "2",
    3: "3",
    4: "4 (normal)",
    5: "5",
    6: "6 (high)",
    7: "7 (top)",
}


def parse_priority_value(val: str) -> int:
    v = str(val).strip().lower()
    if v in PRIORITY_ALIASES:
        return PRIORITY_ALIASES[v]
    try:
        p = int(v)
        if 0 <= p <= 7:
            return p
    except ValueError:
        pass
    raise click.BadParameter(
        f"Invalid priority '{val}'. Valid options: 0..7, 'skip', 'low', 'normal', 'top'."
    )


@click.command("files", short_help="Show and manage file priorities for a torrent.")
@click.argument(
    "torrent",
    required=False,
    metavar="[INFO-HASH|NAME]",
    shell_complete=complete_torrent_identifiers,
)
@click.option(
    "-p",
    "--set-priority",
    "set_priority",
    nargs=2,
    type=str,
    multiple=True,
    help="Set priority for a file: index priority (e.g. -p 0 7 or -p 1 skip)",
)
@click.option(
    "--skip",
    "skip_files",
    type=int,
    multiple=True,
    help="File index(es) to skip downloading (priority 0).",
)
@click.option(
    "--normal",
    "normal_files",
    type=int,
    multiple=True,
    help="File index(es) to set to normal priority (priority 4).",
)
@click.option(
    "--top",
    "top_files",
    type=int,
    multiple=True,
    help="File index(es) to set to top priority (priority 7).",
)
@click.option(
    "--all",
    "all_priority",
    type=str,
    default=None,
    help="Set priority for all files in the torrent.",
)
@click.option("--header/--no-header", default=True, help="Print header in output.")
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(
    client,
    torrent,
    set_priority,
    skip_files,
    normal_files,
    top_files,
    all_priority,
    header,
    json_output,
    plain,
):
    if set_priority or skip_files or normal_files or top_files or all_priority is not None:
        client.do_command(
            setter,
            torrent=torrent,
            set_priority=set_priority,
            skip_files=skip_files,
            normal_files=normal_files,
            top_files=top_files,
            all_priority=all_priority,
        )
    else:
        client.do_command(
            show,
            torrent=torrent,
            header=header,
            json_output=json_output,
            plain=plain,
        )


async def setter(
    client,
    torrent,
    set_priority,
    skip_files,
    normal_files,
    top_files,
    all_priority,
    **kwargs,
):
    if not torrent:
        print_error("Specify a torrent to update file priorities.", color_opt=getattr(client, "color", None))
        sys.exit(1)

    info_hash = await resolve_single_torrent(client, torrent)

    async with client.session.get(client.url(f"torrent/{info_hash}/files")) as resp:
        if resp.status != 200:
            err = await get_response_error(resp)
            print_error(f"Error fetching files for {torrent}: {err}", color_opt=getattr(client, "color", None))
            sys.exit(1)
        files = await resp.json()

    num_files = len(files)
    updates = {}

    if all_priority is not None:
        prio = parse_priority_value(all_priority)
        for i in range(num_files):
            updates[i] = prio

    for idx in skip_files:
        updates[idx] = 0

    for idx in normal_files:
        updates[idx] = 4

    for idx in top_files:
        updates[idx] = 7

    for idx_str, prio_str in set_priority:
        try:
            idx = int(idx_str)
        except ValueError:
            print_error(f"Invalid file index '{idx_str}'", color_opt=getattr(client, "color", None))
            sys.exit(1)
        prio = parse_priority_value(prio_str)
        updates[idx] = prio

    for idx, prio in updates.items():
        if not (0 <= idx < num_files):
            print_error(
                f"File index {idx} out of range [0, {num_files - 1}].",
                color_opt=getattr(client, "color", None),
            )
            sys.exit(1)

    payload = {str(k): v for k, v in updates.items()}
    async with client.session.put(
        client.url(f"torrent/{info_hash}/files"), json=payload
    ) as resp:
        if resp.status != 200:
            err = await get_response_error(resp)
            print_error(f"Error updating file priorities: {err}", color_opt=getattr(client, "color", None))
            sys.exit(1)

        print_success(
            f"Updated priorities for {len(updates)} file(s) in {torrent}.",
            color_opt=getattr(client, "color", None),
        )


async def show(client, torrent, header=True, json_output=False, plain=False, **kwargs):
    if not torrent:
        print_error("Specify a torrent to view files.", color_opt=getattr(client, "color", None))
        sys.exit(1)

    info_hash = await resolve_single_torrent(client, torrent)

    async with client.session.get(client.url(f"torrent/{info_hash}/files")) as resp:
        if resp.status != 200:
            err = await get_response_error(resp)
            print_error(f"Error getting files for {torrent}: {err}", color_opt=getattr(client, "color", None))
            sys.exit(1)
        files = await resp.json()

    if json_output:
        print_json(files)
        return

    is_interactive = should_use_color(getattr(client, "color", None)) and not plain

    if is_interactive:
        console = get_console(getattr(client, "color", None))
        theme = getattr(client, "theme", "modern")
        table = Table(
            box=get_box_style(theme),
            border_style=get_border_style(theme),
            show_header=header,
            caption_style="none",
            header_style=HEADER_STYLE,
        )
        table.add_column("Index", justify="right", style="dim", no_wrap=True)
        table.add_column("Priority", justify="left", no_wrap=True)
        table.add_column("Progress", justify="right", no_wrap=True)
        table.add_column("Done / Size", justify="right", no_wrap=True)
        table.add_column("Path", justify="left")

        for f in files:
            prio = f.get("priority", 4)
            prio_label = PRIORITY_NAMES.get(prio, str(prio))
            if prio == 0:
                prio_style = "dim"
            elif prio >= 6:
                prio_style = "bold green"
            else:
                prio_style = "blue"

            prog = f.get("progress", 0.0)
            prog_pct = f"{prog * 100:.1f}%"
            size_str = f"{format_bytes(f.get('done', 0))} / {format_bytes(f.get('size', 0))}"
            path_str = f.get("path", "")

            table.add_row(
                str(f.get("index", 0)),
                f"[{prio_style}]{prio_label}[/{prio_style}]",
                prog_pct,
                size_str,
                path_str,
            )

        console.print(table)
    else:
        headers = ["Index", "Priority", "Progress", "Done", "Size", "Path"] if header else []
        rows = []
        for f in files:
            prio = f.get("priority", 4)
            prio_label = PRIORITY_NAMES.get(prio, str(prio))
            prog = f.get("progress", 0.0)
            rows.append([
                f.get("index", 0),
                prio_label,
                f"{prog * 100:.1f}%",
                format_bytes(f.get("done", 0), human=False),
                format_bytes(f.get("size", 0), human=False),
                f.get("path", ""),
            ])
        click.echo(tabulate(rows, headers=headers, tablefmt="plain"))
