import aiohttp
import asyncio
import sys
import json
from typing import Tuple

import click
from tabulate import tabulate
from spritzle_cli.main import pass_context


@click.command('settings',
               short_help='Show and modify settings of the session.')
@click.option('--set', '-s', 'set_value', type=str, nargs=2, multiple=True,
              help='Set a property value as: key value')
@pass_context
def main(ctx, set_value):
    loop = asyncio.get_event_loop()
    if set_value:
        loop.run_until_complete(setter(ctx.host, ctx.port, set_value))
    else:
        loop.run_until_complete(show(ctx.host, ctx.port))


async def setter(host, port, set_value):
    data = json.dumps(dict(set_value))
    async with aiohttp.ClientSession() as session:
        url = f'http://{host}:{port}/settings'
        async with session.put(url, data=data) as resp:
            if resp.status != 200:
                click.echo(f'Error: {resp}', file=sys.stderr)
                sys.exit(1)


async def show(host, port):
    async with aiohttp.ClientSession() as session:
        async with session.get(f'http://{host}:{port}/settings') as resp:
            if resp.status != 200:
                click.echo(f'Error: {resp}', file=sys.stderr)
                sys.exit(1)

            settings = await resp.json()
            table = []
            for k, v in sorted(settings.items()):
                table.append([k, v])

            print(tabulate(table, tablefmt='plain'))
