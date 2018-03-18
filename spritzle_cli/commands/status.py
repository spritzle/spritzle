import sys

import click
from tabulate import tabulate


@click.command('status', short_help='Show status of the session.')
@click.pass_obj
def main(ctx):
    ctx.do_command(f)


async def f(ctx):
    async with ctx.session.get(ctx.url('session')) as resp:
        if resp.status != 200:
            click.echo(f'Error: {resp}', file=sys.stderr)
            sys.exit(1)

        status = await resp.json()

        table = []
        for k, v in sorted(status.items()):
            table.append([k, v])

        print(tabulate(table, tablefmt='plain'))
