import sys

import click


@click.command("move_storage", short_help="Move torrent storage to a new path.")
@click.argument("info-hash", required=True)
@click.argument("path", required=True)
@click.pass_obj
def command(client, info_hash, path):
    client.do_command(f, info_hash, path)


async def f(client, info_hash, path):
    url = client.url(f"torrent/{info_hash}/move_storage")
    async with client.session.post(url, json=[path]) as resp:
        if resp.status != 200:
            click.echo(
                f"Error moving storage: {resp.status} {resp.reason}", file=sys.stderr
            )
            sys.exit(1)
        click.echo(f"Moved storage for {info_hash} to {path}.")
