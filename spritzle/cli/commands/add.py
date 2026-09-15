from base64 import b64encode
from pathlib import Path
import sys
from urllib.parse import urlparse

import click


from spritzle.cli.display import print_error, print_success


@click.command("add", short_help="Add a torrent to the session.")
@click.argument("path", required=True)
@click.option(
    "--option",
    "-o",
    type=str,
    multiple=True,
    help=(
        "A key=value pair to be passed to the add torrent "
        "parameters. Can be specified multiple times."
    ),
)
@click.option(
    "--tag",
    "-t",
    type=str,
    multiple=True,
    help=("Tag to apply to the torrent. Can be specified multiple times."),
)
@click.option("--quiet", "-Q", is_flag=True, default=False, help="Print only added info-hash.")
@click.pass_obj
def command(client, path, option, tag, quiet):
    client.do_command(f, path, option, tag, quiet)


async def f(client, path, option, tag, quiet=False):
    data = {}
    for o in option:
        if "=" in o:
            k, v = o.split("=", 1)
            data[k] = v
        else:
            data[o] = True
    data["spritzle.tags"] = tag

    if urlparse(path).scheme:
        data["url"] = path
    elif len(path) in (40, 64) and not Path(path).exists():
        try:
            int(path, 16)
            data["info_hash"] = path
        except ValueError:
            try:
                with open(path, "rb") as f:
                    data["file"] = b64encode(f.read()).decode("ascii")
            except OSError as e:
                print_error(f"Error reading file '{path}': {e}", color_opt=getattr(client, "color", None))
                sys.exit(1)
    else:
        try:
            with open(path, "rb") as f:
                data["file"] = b64encode(f.read()).decode("ascii")
        except OSError as e:
            print_error(f"Error reading file '{path}': {e}", color_opt=getattr(client, "color", None))
            sys.exit(1)

    async with client.session.post(client.url("torrent"), json=data) as resp:
        if resp.status != 201:
            print_error(
                f"Error adding torrent: {resp.status} {resp.reason}",
                color_opt=getattr(client, "color", None),
            )
            sys.exit(1)
        location = resp.headers.get("Location")
        if location:
            hash = location.split("/")[-1]
        else:
            resp_data = await resp.json()
            hash = resp_data.get("info_hash", "")

        if quiet:
            click.echo(hash)
        else:
            print_success(f"{hash} added successfully.", color_opt=getattr(client, "color", None))
