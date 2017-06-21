import asyncio
import sys

import aiohttp
import click

from spritzle_cli.main import pass_context


@click.command('remove', short_help='Remove a torrent from the session.')
@click.argument('info-hash', required=True)
@click.option('--delete-files', default=False, is_flag=True,
              help='Delete downloaded files.')
@pass_context
def main(ctx, info_hash, delete_files):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(f(ctx.host, ctx.port, info_hash, delete_files))


async def f(host, port, info_hash, delete_files):
    url = f'http://{host}:{port}/torrent/{info_hash}'
    if delete_files:
        url += '?delete_files'

    async with aiohttp.ClientSession() as session:
        async with session.delete(url) as resp:
            if resp.status != 200:
                click.echo(
                    f'Error removing torrent: {resp.status} {resp.reason}',
                    file=sys.stderr
                )
                sys.exit(1)
            click.echo(f'{info_hash} removed successfully.')
