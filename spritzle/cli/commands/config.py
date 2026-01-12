import sys
import json

import click
from tabulate import tabulate


@click.command("config", short_help="Show and modify config of the session.")
@click.option(
    "--set",
    "-s",
    "set_value",
    type=str,
    nargs=2,
    multiple=True,
    help="Set a config value as: key value",
)
@click.pass_obj
def command(client, set_value):
    if set_value:
        client.do_command(setter, set_value)
    else:
        client.do_command(show)


async def setter(client, set_value):
    data = json.dumps(dict(set_value))
    async with client.session.patch(client.url("config"), data=data) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)


async def show(client):
    async with client.session.get(client.url("config")) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)

        config = await resp.json()
        table = []
        for k, v in sorted(config.items()):
            table.append([k, v])

        print(tabulate(table, tablefmt="plain"))
