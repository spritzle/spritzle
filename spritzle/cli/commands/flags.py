import asyncio
import sys

import click
from tabulate import tabulate

from spritzle.cli.display import (
    get_console,
    get_response_error,
    print_error,
    print_json,
    render_kv_table,
    should_use_color,
)
from spritzle.cli.lookup import resolve_single_torrent, resolve_target_torrents


@click.command("flags", short_help="Show and modify torrent flags.")
@click.argument("torrent", required=False, metavar="[INFO-HASH|NAME]")
@click.option("--header/--no-header", default=True, help="Print header in output.")
@click.option("-s", "--sets", help="Set flags.", type=str, multiple=True)
@click.option("-u", "--unsets", help="Unset flags.", type=str, multiple=True)
@click.option("-q", "--query", multiple=True, help="Query string to filter torrents.")
@click.option("--all", "all_torrents", is_flag=True, help="Apply to all torrents.")
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, *args, **kwargs):
    if kwargs["sets"] or kwargs["unsets"]:
        client.do_command(setter, *args, **kwargs)
    else:
        client.do_command(show, *args, **kwargs)


async def setter(client, torrent, header, sets, unsets, query, all_torrents, **kwargs):
    targets = await resolve_target_torrents(
        client, torrent=torrent, query=query, all_torrents=all_torrents
    )
    if not targets:
        click.echo("No matching torrents found.")
        return

    d = {}
    for k in sets:
        d[k] = True
    for k in unsets:
        d[k] = False

    async def _set_flags(ih):
        async with client.session.put(
            client.url(f"torrent/{ih}/flags"), json=d
        ) as resp:
            err = "" if resp.status == 200 else await get_response_error(resp)
            return ih, resp.status == 200, err

    results = await asyncio.gather(*[_set_flags(ih) for ih in targets])
    errors = [(ih, reason) for ih, ok, reason in results if not ok]
    if errors:
        for ih, reason in errors:
            print_error(f"Error setting flags on {ih}: {reason}", color_opt=getattr(client, "color", None))
        sys.exit(1)


async def show(client, torrent, header, json_output=False, plain=False, **kwargs):
    if not torrent:
        print_error("Specify a torrent to show flags.", color_opt=getattr(client, "color", None))
        sys.exit(1)

    info_hash = await resolve_single_torrent(client, torrent)

    async with client.session.get(client.url(f"torrent/{info_hash}/flags")) as resp:
        if resp.status != 200:
            err_msg = await get_response_error(resp)
            print_error(f"Error getting flags for {info_hash}: {err_msg}", color_opt=getattr(client, "color", None))
            sys.exit(1)

        t = await resp.json()

    if json_output:
        print_json(t)
        return

    is_interactive = should_use_color(getattr(client, "color", None)) and not plain

    if is_interactive:
        console = get_console(getattr(client, "color", None))
        render_kv_table(
            console,
            list(t.items()),
            title=f"Torrent Flags ({info_hash})",
            key_header="Flag",
            value_header="Value",
        )
    else:
        table = []
        for key, value in t.items():
            table.append((key, value))
        tablefmt = "simple" if header else "plain"
        headers = ["flag", "value"] if header else []
        print(tabulate(table, headers=headers, tablefmt=tablefmt))


