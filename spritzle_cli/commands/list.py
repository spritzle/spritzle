import aiohttp
import asyncio
import sys

import click
from tabulate import tabulate
from spritzle_cli.main import pass_context


@click.command('list', short_help='List torrents in the session.')
@click.option('-f', '--fields', type=str, show_default=True,
              default=('name,state,progress,download_rate,upload_rate,'
                       'spritzle.tags'),
              help='Fields from the torrent status that will be printed.')
@click.option('--header/--no-header', default=True,
              help='Print header in output.')
@pass_context
def main(ctx, fields, header):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(f(ctx.host, ctx.port, fields, header))


async def f(host, port, fields, header):
    type_formatters = {
        list: list_formatter,
    }

    fields = fields.split(',')
    async with aiohttp.ClientSession() as session:
        async with session.get(f'http://{host}:{port}/torrent') as resp:
            if resp.status != 200:
                click.echo('Error: {resp}', file=sys.stderr)
                sys.exit(1)
            torrents = await resp.json()

        table = []
        for torrent in torrents:
            url = f'http://{host}:{port}/torrent/{torrent}'
            async with session.get(url) as resp:
                t = await resp.json()
                values = []
                for field in fields:
                    value = t[field]
                    values.append(
                        type_formatters.get(type(value), str)(value))
                table.append(values)

        tablefmt = 'simple'
        if not header:
            fields = []
            tablefmt = 'plain'

        print(tabulate(table, headers=fields, tablefmt=tablefmt))


def list_formatter(v):
    return ','.join(v)
