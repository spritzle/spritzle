import sys
from typing import Any, Dict, List

import click
from tabulate import tabulate

from spritzle.cli.display import (
    format_bool,
    format_bytes,
    format_progress,
    format_speed,
    format_state,
    get_console,
    print_json,
    render_rich_table,
    should_use_color,
)


@click.command("list", short_help="List torrents in the session.")
@click.option(
    "-f",
    "--fields",
    type=str,
    show_default=True,
    default=("name,state,progress,download_rate,upload_rate,spritzle.tags"),
    help="Fields from the torrent status that will be printed.",
)
@click.option("--header/--no-header", default=True, help="Print header in output.")
@click.option(
    "-q",
    "--query",
    type=str,
    multiple=True,
    help="Query string used to filter the torrents. Format should be <field[.(lt|gt|ne|ge|le)]>=<value>.",
)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--raw", is_flag=True, default=False, help="Print raw unformatted values.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, fields, header, query, json_output, raw, plain):
    client.do_command(f, fields, header, query, json_output, raw, plain)


async def f(
    client,
    fields: str,
    header: bool,
    query: List[str],
    json_output: bool = False,
    raw: bool = False,
    plain: bool = False,
):
    type_formatters = {list: list_formatter}

    params = {}
    for q in query:
        if "=" in q:
            k, v = q.split("=", 1)
            params[k] = v
        else:
            params[q] = ""
    field_list: List[str] = [f.strip() for f in fields.split(",") if f.strip()]
    async with client.session.get(client.url("torrent"), params=params) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)
        torrents = await resp.json()

    raw_items: List[Dict[str, Any]] = []
    for torrent in torrents:
        async with client.session.get(client.url(f"torrent/{torrent}")) as resp:
            if resp.status != 200:
                continue
            t = await resp.json()
            if not isinstance(t, dict):
                continue
            raw_items.append(t)

    if json_output:
        json_data = []
        for item in raw_items:
            json_data.append({f: item.get(f, None) for f in field_list})
        print_json(json_data)
        return

    is_interactive = should_use_color(getattr(client, "color", None)) and not plain and not raw

    table = []
    for item in raw_items:
        values = []
        for field in field_list:
            val = item.get(field, "")
            if is_interactive:
                if field in ("download_rate", "upload_rate"):
                    formatted_val = format_speed(val, human=True)
                elif field in ("total_done", "total_wanted", "total_size", "all_time_upload", "all_time_download"):
                    formatted_val = format_bytes(val, human=True)
                elif field == "progress":
                    formatted_val = format_progress(val, human=True)
                elif field == "state":
                    formatted_val = format_state(str(val), use_color=True)
                elif isinstance(val, bool):
                    formatted_val = format_bool(val, human=True, use_color=True)
                elif isinstance(val, list):
                    formatted_val = list_formatter(val)
                else:
                    formatted_val = str(val)
                values.append(formatted_val)
            else:
                values.append(type_formatters.get(type(val), str)(val))
        table.append(values)

    if is_interactive:
        console = get_console(getattr(client, "color", None))
        headers = field_list if header else []
        render_rich_table(console, headers, table)
    else:
        tablefmt = "simple" if header else "plain"
        headers = field_list if header else []
        print(tabulate(table, headers=headers, tablefmt=tablefmt))


def list_formatter(v):
    return ",".join(str(x) for x in v)


