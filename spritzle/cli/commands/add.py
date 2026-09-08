from base64 import b64encode
from pathlib import Path
import sys
from urllib.parse import urlparse

import click


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
@click.pass_obj
def command(client, path, option, tag):
    client.do_command(f, path, option, tag)


async def f(client, path, option, tag):
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
                click.echo(f"Error reading file '{path}': {e}", file=sys.stderr)
                sys.exit(1)
    else:
        try:
            with open(path, "rb") as f:
                data["file"] = b64encode(f.read()).decode("ascii")
        except OSError as e:
            click.echo(f"Error reading file '{path}': {e}", file=sys.stderr)
            sys.exit(1)

    async with client.session.post(client.url("torrent"), json=data) as resp:
        if resp.status != 201:
            click.echo(
                f"Error adding torrent: {resp.status} {resp.reason}", file=sys.stderr
            )
            sys.exit(1)
        location = resp.headers.get("Location")
        if location:
            hash = location.split("/")[-1]
        else:
            resp_data = await resp.json()
            hash = resp_data.get("info_hash", "")
        click.echo(f"{hash} added successfully.")
