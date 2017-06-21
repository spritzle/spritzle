from urllib.parse import urlparse
import asyncio
import json
import sys
from typing import List, Dict, Any

import aiohttp
import click

from spritzle_cli.main import pass_context


@click.command('add', short_help='Add a torrent to the session.')
@click.argument('path', required=True)
@click.option('--option', '-o', type=str, multiple=True,
              help=('A key=value pair to be passed to the add torrent '
                    'parameters. Can be specified multiple times.'))
@click.option('--tag', '-t', type=str, multiple=True,
              help=('Tag to apply to the torrent. Can be specified multiple '
                    'times.'))
@pass_context
def main(ctx, path, option, tag):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(f(ctx.host, ctx.port, path, option, tag))


async def f(host, port, path, option, tag):
    args = dict([o.split('=') for o in option])
    data = {
        'args': json.dumps(args),
        'tags': json.dumps(tag),
    }

    if not urlparse(path).scheme:
        data['file'] = open(path, 'rb')
    else:
        data['url'] = path

    async with aiohttp.ClientSession() as session:
        url = f'http://{host}:{port}/torrent'
        async with session.post(url, data=data) as resp:
            if resp.status != 201:
                click.echo(
                    f'Error adding torrent: {resp.status} {resp.reason}',
                    file=sys.stderr
                )
                sys.exit(1)
            hash = resp.headers['Location'].split('/')[-1]
            click.echo(f'{hash} added successfully.')
