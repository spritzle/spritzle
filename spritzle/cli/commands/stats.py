import sys

import click
from tabulate import tabulate


@click.command('stats', short_help='Show session statistics.')
@click.pass_obj
def command(client):
    client.do_command(f)


async def f(client):
    async with client.session.get(client.url('session/stats')) as resp:
        if resp.status != 200:
            click.echo(f'Error: {resp}', file=sys.stderr)
            sys.exit(1)

        status = await resp.json()

        table = []
        for k, v in sorted(status.items()):
            table.append([k, v])

        print(tabulate(table, tablefmt='plain'))
