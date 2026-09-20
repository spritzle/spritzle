#
# spritzle/cli/commands/status.py
#
# Copyright (C) 2026 Andrew Resch <andrewresch@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.    If not, write to:
#   The Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor
#   Boston, MA    02110-1301, USA.
#

import sys
import time
from typing import Any, Dict

import aiohttp
import click

from spritzle.cli.display import (
    get_console,
    get_response_error,
    print_error,
    print_json,
    render_plain_table,
    render_status_card,
)


def format_uptime(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h}h {m}m"
    d, h = divmod(h, 24)
    return f"{d}d {h}h"


@click.command("status", short_help="Show daemon health and connection status.")
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, json_output, plain):
    """Show daemon health, latency, uptime, and identity status."""
    client.do_command(f, json_output, plain)


async def f(client, json_output: bool = False, plain: bool = False):
    color_opt = getattr(client, "color", None)
    remote_name = getattr(client, "remote_name", "local") or "local"
    url = client.url("status")

    start = time.perf_counter()
    try:
        async with client.session.get(url) as resp:
            latency_ms = round((time.perf_counter() - start) * 1000, 1)
            if resp.status == 401:
                print_error(
                    f"Authentication failed for remote '{remote_name}' (HTTP 401 Unauthorized).\n"
                    f"Update the API key with: spritzle remote set-key {remote_name}",
                    color_opt=color_opt,
                )
                sys.exit(1)
            if resp.status != 200:
                err_msg = await get_response_error(resp)
                print_error(f"Daemon returned HTTP {resp.status}: {err_msg}", color_opt=color_opt)
                sys.exit(1)

            data: Dict[str, Any] = await resp.json()
    except aiohttp.ClientConnectorCertificateError as e:
        print_error(
            f"TLS certificate verification failed for {url}: {e.certificate_error}\n"
            "If using a self-signed certificate, update the remote with --fingerprint, --ca-cert, or --insecure.",
            color_opt=color_opt,
        )
        sys.exit(1)
    except aiohttp.ClientConnectorError:
        print_error(
            f"Could not connect to spritzled at {client.url('')}. Is the daemon running? (Run 'spritzled' to start it).",
            color_opt=color_opt,
        )
        sys.exit(1)

    daemon_id = data.get("daemon_id", "unknown")
    version = data.get("version", "unknown")
    uptime_sec = float(data.get("uptime", 0.0))
    uptime_str = format_uptime(uptime_sec)
    num_torrents = int(data.get("num_torrents", 0))

    if json_output:
        print_json({
            "remote": remote_name,
            "status": "online",
            "url": client.url(""),
            "daemon_id": daemon_id,
            "version": version,
            "latency_ms": latency_ms,
            "uptime": uptime_sec,
            "uptime_formatted": uptime_str,
            "num_torrents": num_torrents,
        })
        return

    if plain:
        rows = [
            ["remote", remote_name],
            ["status", "online"],
            ["url", client.url("")],
            ["daemon_id", daemon_id],
            ["version", version],
            ["latency_ms", f"{latency_ms} ms"],
            ["uptime", uptime_str],
            ["num_torrents", num_torrents],
        ]
        render_plain_table(["Field", "Value"], rows, header=False)
        return

    console = get_console(color_opt)
    theme = getattr(client, "theme", "modern")
    render_status_card(
        console=console,
        remote_name=remote_name,
        url=client.url(""),
        daemon_id=daemon_id,
        version=version,
        latency_ms=latency_ms,
        uptime_str=uptime_str,
        num_torrents=num_torrents,
        color_opt=color_opt,
        theme=theme,
    )
