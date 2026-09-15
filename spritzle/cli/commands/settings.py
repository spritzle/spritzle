import json
import sys

import click
from tabulate import tabulate

from spritzle.cli.display import (
    get_console,
    print_json,
    render_rich_table,
    should_use_color,
)


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
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, set_value, json_output, plain):
    if set_value:
        client.do_command(setter, set_value)
    else:
        client.do_command(show, json_output, plain)


async def setter(client, set_value):
    d = {}
    for k, v in set_value:
        try:
            d[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError, ValueError):
            d[k] = v
    headers = {"Content-Type": "application/json"}
    async with client.session.put(
        client.url("session/settings"), json=d, headers=headers
    ) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)


async def show(client, json_output=False, plain=False):
    async with client.session.get(client.url("session/settings")) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)

        settings = await resp.json()

    if json_output:
        print_json(settings)
        return

    table = []
    for k, v in sorted(settings.items()):
        table.append([k, v])

    if should_use_color(getattr(client, "color", None)) and not plain:
        console = get_console(getattr(client, "color", None))
        render_rich_table(console, ["Setting", "Value"], table, title="Session Settings")
    else:
        print(tabulate(table, tablefmt="plain"))

