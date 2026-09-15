import asyncio
import sys

import click

from spritzle.cli.lookup import resolve_target_torrents


@click.command("resume", short_help="Resume a torrent.")
@click.argument("torrent", required=False, metavar="[INFO-HASH|NAME]")
@click.option("-q", "--query", multiple=True, help="Query string to filter torrents.")
@click.option("--all", "all_torrents", is_flag=True, help="Resume all torrents.")
@click.pass_obj
def command(client, torrent, query, all_torrents):
    client.do_command(f, torrent, query, all_torrents)


async def f(client, torrent, query, all_torrents):
    targets = await resolve_target_torrents(
        client, torrent=torrent, query=query, all_torrents=all_torrents
    )
    if not targets:
        click.echo("No matching torrents found.")
        return

    async def _resume(ih):
        url = client.url(f"torrent/{ih}/resume")
        async with client.session.post(url, json=[]) as resp:
            return ih, resp.status == 200, resp.reason

    results = await asyncio.gather(*[_resume(ih) for ih in targets])
    errors = [(ih, reason) for ih, ok, reason in results if not ok]
    if errors:
        for ih, reason in errors:
            click.echo(f"Error resuming {ih}: {reason}", file=sys.stderr)
        sys.exit(1)

    if len(targets) == 1 and not (query or all_torrents):
        click.echo(f"{targets[0]} resumed successfully.")
    else:
        click.echo(f"Resumed {len(targets)} torrents successfully.")
