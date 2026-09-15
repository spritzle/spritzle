import asyncio
import sys

import click

from spritzle.cli.display import print_error, print_success
from spritzle.cli.lookup import resolve_target_torrents


@click.command("remove", short_help="Remove a torrent from the session.")
@click.argument("torrent", required=False, metavar="[INFO-HASH|NAME]")
@click.option(
    "--delete-files", default=False, is_flag=True, help="Delete downloaded files."
)
@click.option("-q", "--query", multiple=True, help="Query string to filter torrents.")
@click.option("--all", "all_torrents", is_flag=True, help="Remove all torrents.")
@click.option("--quiet", "-Q", is_flag=True, default=False, help="Print only affected info-hashes.")
@click.pass_obj
def command(client, torrent, delete_files, query, all_torrents, quiet):
    client.do_command(f, torrent, delete_files, query, all_torrents, quiet)


async def f(client, torrent, delete_files, query, all_torrents, quiet=False):
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
            print_error(f"Error removing {ih}: {reason}", color_opt=getattr(client, "color", None))
        sys.exit(1)

    if quiet:
        for ih in targets:
            click.echo(ih)
        return

    color_opt = getattr(client, "color", None)
    if len(targets) == 1 and not (query or all_torrents):
        print_success(f"{targets[0]} removed successfully.", color_opt=color_opt)
    else:
        print_success(f"Removed {len(targets)} torrents successfully.", color_opt=color_opt)

