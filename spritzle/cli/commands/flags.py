import json
import sys

import click
from tabulate import tabulate


@click.command("flags", short_help="Show and modify torrent flags.")
@click.argument("info-hash", required=True)
@click.option("--header/--no-header", default=True, help="Print header in output.")
@click.option("-s", "--sets", help="Set flags.", type=str, multiple=True)
@click.option("-u", "--unsets", help="Unset flags.", type=str, multiple=True)
@click.pass_obj
def command(client, *args, **kwargs):
    if kwargs["sets"] or kwargs["unsets"]:
        client.do_command(setter, *args, **kwargs)
    else:
        client.do_command(show, *args, **kwargs)


async def setter(client, info_hash, header, sets, unsets):
    d = {}
    for k in sets:
        d[k] = True
    for k in unsets:
        d[k] = False
    data = json.dumps(d)
    async with client.session.put(
        client.url(f"torrent/{info_hash}/flags"), data=data
    ) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)


async def show(client, info_hash, header, **kwargs):
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


def list_formatter(v):
    return ",".join(v)
