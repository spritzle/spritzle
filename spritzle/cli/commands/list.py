import sys
from typing import List

import click
from tabulate import tabulate


@click.command("list", short_help="List torrents in the session.")
@click.option(
    "-f",
    "--fields",
    type=str,
    show_default=True,
    default=("name,state,progress,download_rate,upload_rate," "spritzle.tags"),
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
@click.pass_obj
def command(client, fields, header, query):
    client.do_command(f, fields, header, query)


async def f(client, fields: str, header: bool, query: List[str]):
    type_formatters = {list: list_formatter}

    params = dict([q.split("=") for q in query])
    fields: List[str] = fields.split(",")
    async with client.session.get(client.url("torrent"), params=params) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)
        torrents = await resp.json()

    table = []
    for torrent in torrents:
        async with client.session.get(client.url(f"torrent/{torrent}")) as resp:
            t = await resp.json()
            values = []
            for field in fields:
                value = t[field]
                values.append(type_formatters.get(type(value), str)(value))
            table.append(values)

    tablefmt = "simple"
    if not header:
        fields = []
        tablefmt = "plain"

    print(tabulate(table, headers=fields, tablefmt=tablefmt))


def list_formatter(v):
    return ",".join(v)
