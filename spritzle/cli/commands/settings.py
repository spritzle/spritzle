import sys
import json

import click
from tabulate import tabulate


@click.command("settings", short_help="Show and modify settings of the session.")
@click.option(
    "--set",
    "-s",
    "set_value",
    type=str,
    nargs=2,
    multiple=True,
    help="Set a property value as: key value",
)
@click.pass_obj
def command(client, set_value):
    if set_value:
        client.do_command(setter, set_value)
    else:
        client.do_command(show)


async def setter(client, set_value):
    data = json.dumps(dict(set_value))
    async with client.session.put(client.url("session/settings"), data=data) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)


async def show(client):
    async with client.session.get(client.url("session/settings")) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)

        settings = await resp.json()
        table = []
        for k, v in sorted(settings.items()):
            table.append([k, v])

        print(tabulate(table, tablefmt="plain"))
