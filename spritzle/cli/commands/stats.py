import sys

import click
from tabulate import tabulate

from spritzle.cli.display import (
    get_console,
    print_json,
    render_rich_table,
    should_use_color,
)


@click.command("stats", short_help="Show session statistics.")
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, json_output, plain):
    client.do_command(f, json_output, plain)


async def f(client, json_output=False, plain=False):
    async with client.session.get(client.url("session/stats")) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)

        status = await resp.json()

    if json_output:
        print_json(status)
        return

    table = []
    for k, v in sorted(status.items()):
        table.append([k, v])

    if should_use_color(getattr(client, "color", None)) and not plain:
        console = get_console(getattr(client, "color", None))
        render_rich_table(console, ["Statistic", "Value"], table, title="Session Statistics")
    else:
        print(tabulate(table, tablefmt="plain"))

