import aiohttp
import asyncio
import sys

import click
from tabulate import tabulate
from spritzle_cli.main import pass_context


@click.command('status', short_help='Show status of the session.')
@pass_context
def main(ctx):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(f(ctx.host, ctx.port))


async def f(host, port):
    async with aiohttp.ClientSession() as session:
        async with session.get(f'http://{host}:{port}/session') as resp:
            if resp.status != 200:
                click.echo(f'Error: {resp}', file=sys.stderr)
                sys.exit(1)

            status = await resp.json()

            table = []
            for k, v in sorted(status.items()):
                table.append([k, v])

            print(tabulate(table, tablefmt='plain'))
