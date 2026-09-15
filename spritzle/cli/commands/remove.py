import asyncio
import sys

import click

from spritzle.cli.lookup import resolve_target_torrents


@click.command("remove", short_help="Remove a torrent from the session.")
@click.argument("torrent", required=False, metavar="[INFO-HASH|NAME]")
@click.option(
    "--delete-files", default=False, is_flag=True, help="Delete downloaded files."
)
@click.option("-q", "--query", multiple=True, help="Query string to filter torrents.")
@click.option("--all", "all_torrents", is_flag=True, help="Remove all torrents.")
@click.pass_obj
def command(client, torrent, delete_files, query, all_torrents):
    client.do_command(f, torrent, delete_files, query, all_torrents)


async def f(client, torrent, delete_files, query, all_torrents):
    targets = await resolve_target_torrents(
        client, torrent=torrent, query=query, all_torrents=all_torrents
    )
    if not targets:
        click.echo("No matching torrents found.")
        return

    params = {}
    if delete_files:
        params["delete_files"] = ""

    async def _remove(ih):
        url = client.url(f"torrent/{ih}")
        async with client.session.delete(url, params=params) as resp:
            return ih, resp.status == 200, resp.reason

    results = await asyncio.gather(*[_remove(ih) for ih in targets])
    errors = [(ih, reason) for ih, ok, reason in results if not ok]
    if errors:
        for ih, reason in errors:
            click.echo(f"Error removing {ih}: {reason}", file=sys.stderr)
        sys.exit(1)

    if len(targets) == 1 and not (query or all_torrents):
        click.echo(f"{targets[0]} removed successfully.")
    else:
        click.echo(f"Removed {len(targets)} torrents successfully.")
