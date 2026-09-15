import asyncio
import sys

import click
from tabulate import tabulate

from spritzle.cli.lookup import resolve_single_torrent, resolve_target_torrents


@click.command("flags", short_help="Show and modify torrent flags.")
@click.argument("torrent", required=False, metavar="[INFO-HASH|NAME]")
@click.option("--header/--no-header", default=True, help="Print header in output.")
@click.option("-s", "--sets", help="Set flags.", type=str, multiple=True)
@click.option("-u", "--unsets", help="Unset flags.", type=str, multiple=True)
@click.option("-q", "--query", multiple=True, help="Query string to filter torrents.")
@click.option("--all", "all_torrents", is_flag=True, help="Apply to all torrents.")
@click.pass_obj
def command(client, *args, **kwargs):
    if kwargs["sets"] or kwargs["unsets"]:
        client.do_command(setter, *args, **kwargs)
    else:
        client.do_command(show, *args, **kwargs)


async def setter(client, torrent, header, sets, unsets, query, all_torrents):
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
            return ih, resp.status == 200, resp.reason

    results = await asyncio.gather(*[_set_flags(ih) for ih in targets])
    errors = [(ih, reason) for ih, ok, reason in results if not ok]
    if errors:
        for ih, reason in errors:
            click.echo(f"Error setting flags on {ih}: {reason}", file=sys.stderr)
        sys.exit(1)


async def show(client, torrent, header, **kwargs):
    if not torrent:
        click.echo("Error: Specify a torrent to show flags.", file=sys.stderr)
        sys.exit(1)

    info_hash = await resolve_single_torrent(client, torrent)

    table = []
    async with client.session.get(client.url(f"torrent/{info_hash}/flags")) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)

        t = await resp.json()
        for key, value in t.items():
            table.append((key, value))

    tablefmt = "simple"
    headers = ["flag", "value"]
    if not header:
        headers = []
        tablefmt = "plain"

    print(tabulate(table, headers=headers, tablefmt=tablefmt))

