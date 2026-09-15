import json
import sys

import click
from tabulate import tabulate

from spritzle.cli.display import (
    get_console,
    print_error,
    print_json,
    render_kv_table,
    should_use_color,
)


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
    async with client.session.patch(client.url("config"), json=d) as resp:
        if resp.status != 200:
            print_error(f"Error: {resp}", color_opt=getattr(client, "color", None))
            sys.exit(1)


async def show(client, json_output=False, plain=False):
    async with client.session.get(client.url("config")) as resp:
        if resp.status != 200:
            print_error(f"Error: {resp}", color_opt=getattr(client, "color", None))
            sys.exit(1)

        config = await resp.json()

    if json_output:
        print_json(config)
        return

    table = []
    for k, v in sorted(config.items()):
        table.append([k, v])

    if should_use_color(getattr(client, "color", None)) and not plain:
        console = get_console(getattr(client, "color", None))
        render_kv_table(
            console,
            table,
            title="Spritzle Configuration",
            key_header="Option",
            value_header="Value",
        )
    else:
        print(tabulate(table, tablefmt="plain"))

