from base64 import b64encode
import os
from pathlib import Path
import re
import sys
from typing import Sequence
from urllib.parse import parse_qs, urlparse

import click

from spritzle.cli.display import (
    get_console,
    get_response_error,
    print_error,
    print_json,
    print_warning,
    render_post_add_card,
)


@click.command("add", short_help="Add a torrent to the session.")
@click.argument("path", required=True, type=click.Path())
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
@click.option(
    "--watch",
    "-w",
    is_flag=True,
    default=False,
    help="Stream live progress until completion or Ctrl+C.",
)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, path, option, tag, quiet, watch, json_output, plain):
    client.do_command(f, path, option, tag, quiet, watch, json_output, plain)


async def f(
    client,
    path: str,
    option: Sequence[str],
    tag: Sequence[str],
    quiet: bool = False,
    watch: bool = False,
    json_output: bool = False,
    plain: bool = False,
):
    data = {}
    for o in option:
        if "=" in o:
            k, v = o.split("=", 1)
            data[k] = v
        else:
            data[o] = True
    data["spritzle.tags"] = tag

    color_opt = getattr(client, "color", None)

    # Stdin input
    if path == "-":
        stdin_bytes = sys.stdin.buffer.read()
        stripped = stdin_bytes.strip()
        if stripped.startswith(b"magnet:") or stripped.startswith(b"http://") or stripped.startswith(b"https://"):
            data["url"] = stripped.decode("utf-8", errors="replace")
        else:
            data["file"] = b64encode(stdin_bytes).decode("ascii")

    # Magnet URI checks
    elif path.startswith("magnet:"):
        parsed = urlparse(path)
        qs = parse_qs(parsed.query)
        if "xt" not in qs:
            print_error(
                "Malformed magnet URI (missing 'xt' parameter).\n"
                "If your magnet link contained '&', it was likely split by your shell.\n"
                "Enclose the URL in single quotes: spritzle add 'magnet:?...'",
                color_opt=color_opt,
            )
            sys.exit(1)
        if path.endswith(("&", "=", "?")):
            print_warning(
                "The magnet URL ends with a trailing symbol ('&', '=', '?') which suggests it was truncated by the shell.",
                color_opt=color_opt,
            )
        if hasattr(os, "getpgrp") and hasattr(os, "tcgetpgrp"):
            try:
                if sys.stdin.isatty() and os.getpgrp() != os.tcgetpgrp(sys.stdin.fileno()):
                    print_warning(
                        "Command is running in the background. If you passed an unquoted magnet link with '&', the URL was likely split.",
                        color_opt=color_opt,
                    )
            except Exception:
                pass
        data["url"] = path

    elif urlparse(path).scheme:
        data["url"] = path

    elif path.startswith(("magnet?", "urn:btih:", "?xt=")):
        print_error(
            f"Malformed magnet link: '{path}'. Ensure the link starts with 'magnet:?xt=' and is enclosed in quotes.",
            color_opt=color_opt,
        )
        sys.exit(1)

    elif len(path) in (40, 64) and not Path(path).exists():
        try:
            int(path, 16)
            data["info_hash"] = path
        except ValueError:
            try:
                with open(path, "rb") as f:
                    data["file"] = b64encode(f.read()).decode("ascii")
            except OSError as e:
                print_error(f"Error reading file '{path}': {e}", color_opt=color_opt)
                sys.exit(1)

    elif re.fullmatch(r"^[0-9a-fA-F]+$", path):
        print_error(
            f"Invalid info-hash length ({len(path)}). Info-hashes must be 40 (SHA-1) or 64 (SHA-256) hex characters.",
            color_opt=color_opt,
        )
        sys.exit(1)

    else:
        try:
            with open(path, "rb") as f:
                data["file"] = b64encode(f.read()).decode("ascii")
        except OSError as e:
            print_error(f"Error reading file '{path}': {e}", color_opt=color_opt)
            sys.exit(1)

    async with client.session.post(client.url("torrent"), json=data) as resp:
        if resp.status != 201:
            err_msg = await get_response_error(resp)
            print_error(
                f"Error adding torrent: {err_msg}",
                color_opt=color_opt,
            )
            sys.exit(1)

        resp_data = {}
        try:
            resp_data = await resp.json()
        except Exception:
            pass

        location = resp.headers.get("Location")
        if location:
            hash = location.split("/")[-1]
        else:
            hash = resp_data.get("info_hash", "")

        resp_data["info_hash"] = hash

        # If name or size wasn't in resp_data (e.g. from an older daemon), fetch it
        if "name" not in resp_data or "size" not in resp_data:
            try:
                async with client.session.get(client.url(f"torrent/{hash}")) as sresp:
                    if sresp.status == 200:
                        sdata = await sresp.json()
                        resp_data.setdefault("name", sdata.get("name", ""))
                        resp_data.setdefault(
                            "size", sdata.get("total_wanted", 0) or sdata.get("total_size", 0)
                        )
                        resp_data.setdefault("save_path", sdata.get("save_path", ""))
                        resp_data.setdefault("state", sdata.get("state", "downloading"))
                        resp_data.setdefault("num_peers", sdata.get("num_peers", 0))
            except Exception:
                pass

        if not resp_data.get("name"):
            if path.startswith("magnet:"):
                qs = parse_qs(urlparse(path).query)
                if "dn" in qs and qs["dn"]:
                    resp_data["name"] = qs["dn"][0]
            elif not path.startswith(("http://", "https://")) and len(path) not in (40, 64):
                try:
                    resp_data["name"] = Path(path).stem
                except Exception:
                    pass
            if not resp_data.get("name"):
                resp_data["name"] = hash

        if quiet:
            click.echo(hash)
            return

        if json_output:
            print_json(resp_data)
            return

        effective_color = color_opt if not plain else False
        console = get_console(effective_color)
        theme = getattr(client, "theme", "modern")
        render_post_add_card(console, resp_data, color_opt=effective_color, theme=theme)

        if watch:
            from spritzle.cli.dashboard import watch_single_torrent

            if effective_color is None or effective_color:
                console.print("")
            await watch_single_torrent(client, hash, color_opt=effective_color)
