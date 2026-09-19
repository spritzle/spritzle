import asyncio
import sys

import click

from spritzle.cli.display import get_response_error, print_error, print_success
from spritzle.cli.lookup import resolve_target_torrents


@click.command("pause", short_help="Pause a torrent.")
@click.argument("torrent", required=False, metavar="[INFO-HASH|NAME]")
@click.option("-q", "--query", multiple=True, help="Query string to filter torrents.")
@click.option("--all", "all_torrents", is_flag=True, help="Pause all torrents.")
@click.option("--quiet", "-Q", is_flag=True, default=False, help="Print only affected info-hashes.")
@click.pass_obj
def command(client, torrent, query, all_torrents, quiet):
    client.do_command(f, torrent, query, all_torrents, quiet)


async def f(client, torrent, query, all_torrents, quiet=False):
    targets = await resolve_target_torrents(
        client, torrent=torrent, query=query, all_torrents=all_torrents
    )
    if not targets:
        click.echo("No matching torrents found.")
        return

    sem = asyncio.Semaphore(32)

    async def _pause(ih):
        async with sem:
            url = client.url(f"torrent/{ih}/pause")
            async with client.session.post(url, json=[]) as resp:
                err = "" if resp.status == 200 else await get_response_error(resp)
                return ih, resp.status == 200, err

    results = await asyncio.gather(*[_pause(ih) for ih in targets])
    errors = [(ih, reason) for ih, ok, reason in results if not ok]
    if errors:
        for ih, reason in errors:
            print_error(f"Error pausing {ih}: {reason}", color_opt=getattr(client, "color", None))
        sys.exit(1)

    if quiet:
        for ih in targets:
            click.echo(ih)
        return

    color_opt = getattr(client, "color", None)
    if len(targets) == 1 and not (query or all_torrents):
        print_success(f"{targets[0]} paused successfully.", color_opt=color_opt)
    else:
        print_success(f"Paused {len(targets)} torrents successfully.", color_opt=color_opt)

