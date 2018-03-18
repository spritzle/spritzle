import sys
import json

import click
from tabulate import tabulate


@click.command('settings',
               short_help='Show and modify settings of the session.')
@click.option('--set', '-s', 'set_value', type=str, nargs=2, multiple=True,
              help='Set a property value as: key value')
@click.pass_obj
def main(ctx, set_value):
    if set_value:
        ctx.do_command(setter, set_value)
    else:
        ctx.do_command(show)


async def setter(ctx, set_value):
    data = json.dumps(dict(set_value))
    async with ctx.session.put(ctx.url('settings'), data=data) as resp:
        if resp.status != 200:
            click.echo(f'Error: {resp}', file=sys.stderr)
            sys.exit(1)


async def show(ctx):
    async with ctx.session.get(ctx.url('settings')) as resp:
        if resp.status != 200:
            click.echo(f'Error: {resp}', file=sys.stderr)
            sys.exit(1)

        settings = await resp.json()
        table = []
        for k, v in sorted(settings.items()):
            table.append([k, v])

        print(tabulate(table, tablefmt='plain'))
