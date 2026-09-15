import sys

import click

from spritzle.cli.lookup import resolve_single_torrent


@click.command("move_storage", short_help="Move torrent storage to a new path.")
@click.argument("torrent", required=True, metavar="[INFO-HASH|NAME]")
@click.argument("path", required=True)
@click.pass_obj
def command(client, torrent, path):
    client.do_command(f, torrent, path)


async def f(client, torrent, path):
    info_hash = await resolve_single_torrent(client, torrent)
    url = client.url(f"torrent/{info_hash}/move_storage")
    async with client.session.post(url, json=[path]) as resp:
        if resp.status != 200:
            click.echo(
                f"Error moving storage: {resp.status} {resp.reason}", file=sys.stderr
            )
            sys.exit(1)
        click.echo(f"Moved storage for {info_hash} to {path}.")
