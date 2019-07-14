import sys

import click


@click.command("remove", short_help="Remove a torrent from the session.")
@click.argument("info-hash", required=True)
@click.option(
    "--delete-files", default=False, is_flag=True, help="Delete downloaded files."
)
@click.pass_obj
def command(client, info_hash, delete_files):
    client.do_command(f, info_hash, delete_files)


async def f(client, info_hash, delete_files):
    url = client.url(f"torrent/{info_hash}")
    if delete_files:
        url += "?delete_files"

    async with client.session.delete(url) as resp:
        if resp.status != 200:
            click.echo(
                f"Error removing torrent: {resp.status} {resp.reason}", file=sys.stderr
            )
            sys.exit(1)
        click.echo(f"{info_hash} removed successfully.")
