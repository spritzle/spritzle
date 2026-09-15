import sys

import click


@click.command("pause", short_help="Pause a torrent.")
@click.argument("info-hash", required=True)
@click.pass_obj
def command(client, info_hash):
    client.do_command(f, info_hash)


async def f(client, info_hash):
    url = client.url(f"torrent/{info_hash}/pause")
    async with client.session.post(url, json=[]) as resp:
        if resp.status != 200:
            click.echo(
                f"Error pausing torrent: {resp.status} {resp.reason}", file=sys.stderr
            )
            sys.exit(1)
        click.echo(f"{info_hash} paused successfully.")
