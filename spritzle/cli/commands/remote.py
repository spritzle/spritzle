#
# spritzle/cli/commands/remote.py
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

import asyncio
import sys
import time
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse

import aiohttp
import click
from rich.markup import escape
from rich.table import Table
from tabulate import tabulate

from spritzle.cli.display import (
    format_latency,
    get_border_style,
    get_box_style,
    get_console,
    print_error,
    print_json,
    print_success,
    render_kv_table,
    should_use_color,
)


def run_coroutine(coro: Any) -> Any:
    """Run an async coroutine using the existing event loop."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def format_uptime(seconds: Union[int, float]) -> str:
    """Format seconds into a compact human-readable uptime string."""
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


async def query_daemon_status(
    url: str,
    key: str,
    timeout_seconds: float = 10.0,
    insecure: bool = False,
    ca_cert: Optional[str] = None,
    fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Connect to daemon at url with key, query /status.
    Returns status dict on success (including latency_ms and daemon_id).
    """
    import ssl

    connector = None
    if insecure:
        connector = aiohttp.TCPConnector(ssl=False)
    elif fingerprint:
        fp_bytes = bytes.fromhex(fingerprint.replace(":", "").strip())
        connector = aiohttp.TCPConnector(fingerprint=fp_bytes)
    elif ca_cert:
        ssl_ctx = ssl.create_default_context(cafile=ca_cert)
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    headers = {"Authorization": f"Bearer {key}"}
    start = time.perf_counter()
    async with aiohttp.ClientSession(timeout=timeout, headers=headers, connector=connector) as session:
        try:
            async with session.get(f"{url}/status") as resp:
                latency_ms = round((time.perf_counter() - start) * 1000, 1)
                if resp.status == 401:
                    raise click.ClickException(
                        f"API key was rejected by daemon at {url} (HTTP 401 Unauthorized)."
                    )
                if resp.status != 200:
                    raise click.ClickException(
                        f"Server at {url} returned HTTP {resp.status} on /status."
                    )
                data = await resp.json()
                daemon_id = resp.headers.get("X-Spritzle-Daemon-Id") or data.get("daemon_id")
                if not daemon_id:
                    raise click.ClickException(f"Invalid response from {url}/status: missing daemon_id.")
                data["daemon_id"] = daemon_id
                data["latency_ms"] = latency_ms
                return data
        except aiohttp.ClientConnectorCertificateError as e:
            raise click.ClickException(
                f"TLS certificate verification failed for {url}: {e.certificate_error}. "
                "Use --fingerprint, --ca-cert, or --insecure."
            )
        except aiohttp.ClientConnectorError as e:
            raise click.ClickException(f"Could not connect to Spritzle daemon at {url}: {e}")


async def check_single_remote_status(name: str, remote_data: Dict[str, Any], is_default: bool) -> Dict[str, Any]:
    url = remote_data.get("url", "")
    key = remote_data.get("key", "")
    expected_daemon_id = remote_data.get("daemon_id")
    insecure = bool(remote_data.get("insecure", False))
    ca_cert = remote_data.get("ca_cert")
    fingerprint = remote_data.get("fingerprint")

    res: Dict[str, Any] = {
        "name": name,
        "url": url,
        "is_default": is_default,
        "status": "unknown",
        "latency_ms": None,
        "version": None,
        "uptime": None,
        "uptime_formatted": None,
        "num_torrents": None,
        "daemon_id": expected_daemon_id,
        "error": None,
    }

    try:
        data = await query_daemon_status(
            url, key, timeout_seconds=5.0, insecure=insecure, ca_cert=ca_cert, fingerprint=fingerprint
        )
        actual_id = data.get("daemon_id")
        if expected_daemon_id and actual_id != expected_daemon_id:
            res["status"] = "id_mismatch"
            res["error"] = f"Daemon identity mismatch: expected {expected_daemon_id}, got {actual_id}"
        else:
            res["status"] = "online"
            res["latency_ms"] = data.get("latency_ms")
            res["version"] = data.get("version")
            res["uptime"] = data.get("uptime")
            res["uptime_formatted"] = format_uptime(data.get("uptime", 0))
            res["num_torrents"] = data.get("num_torrents")
            res["daemon_id"] = actual_id
    except click.ClickException as e:
        err_msg = str(e)
        if "401" in err_msg:
            res["status"] = "auth_failed"
        else:
            res["status"] = "offline"
        res["error"] = err_msg
    except Exception as e:
        res["status"] = "error"
        res["error"] = str(e)

    return res


def normalize_url(raw_url: str) -> str:
    url = raw_url.strip().rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}"
    parsed = urlparse(url)
    if not parsed.hostname:
        raise click.ClickException(f"Invalid URL: '{raw_url}'.")
    return url


@click.group("remote", short_help="Manage remote Spritzle daemons.")
def command():
    """Manage remote Spritzle daemons and API keys."""
    pass


@command.command("add", short_help="Add a remote Spritzle daemon.")
@click.argument("name")
@click.argument("url")
@click.option("-k", "--key", "key", default=None, help="API key for authentication.")
@click.option("--insecure", is_flag=True, default=False, help="Skip TLS certificate verification.")
@click.option("--ca-cert", default=None, type=click.Path(exists=True), help="Path to CA certificate bundle.")
@click.option("--fingerprint", default=None, help="SHA-256 certificate fingerprint.")
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing remote if it exists.",
)
@click.pass_obj
def remote_add(
    client,
    name: str,
    url: str,
    key: Optional[str],
    insecure: bool,
    ca_cert: Optional[str],
    fingerprint: Optional[str],
    force: bool,
):
    """Add a remote Spritzle daemon with its API key."""
    client.remotes.ensure_local_remote()
    existing = client.remotes.get_remote(name)
    if existing and not force:
        print_error(
            f"Remote '{name}' already exists. Use --force or 'remote set-key' to update.",
            color_opt=client.color,
        )
        sys.exit(1)

    normalized_url = normalize_url(url)
    api_key = key
    if not api_key:
        api_key = click.prompt(f"API Key for '{name}'", hide_input=True)

    try:
        status_data = run_coroutine(
            query_daemon_status(
                normalized_url,
                api_key,
                insecure=insecure,
                ca_cert=ca_cert,
                fingerprint=fingerprint,
            )
        )
    except click.ClickException as e:
        print_error(str(e), color_opt=client.color)
        sys.exit(1)

    daemon_id = status_data["daemon_id"]
    client.remotes.set_remote(
        name,
        normalized_url,
        daemon_id,
        api_key,
        insecure=insecure,
        ca_cert=ca_cert,
        fingerprint=fingerprint,
    )
    if not client.remotes.get_default_remote():
        client.remotes.set_default_remote(name)

    print_success(
        f"Added remote '{name}' ({normalized_url}) [Daemon ID: {daemon_id}].",
        color_opt=client.color,
    )


@command.command("set-key", short_help="Update the API key for an existing remote.")
@click.argument("name")
@click.argument("key", required=False, default=None)
@click.pass_obj
def remote_set_key(client, name: str, key: Optional[str]):
    """Update or import the API key for an existing remote."""
    client.remotes.ensure_local_remote()
    remote_data = client.remotes.get_remote(name)
    if not remote_data:
        print_error(f"Remote '{name}' does not exist.", color_opt=client.color)
        sys.exit(1)

    api_key = key
    if not api_key:
        api_key = click.prompt(f"New API Key for '{name}'", hide_input=True)

    url = remote_data["url"]
    expected_daemon_id = remote_data.get("daemon_id")
    insecure = bool(remote_data.get("insecure", False))
    ca_cert = remote_data.get("ca_cert")
    fingerprint = remote_data.get("fingerprint")

    try:
        status_data = run_coroutine(
            query_daemon_status(
                url,
                api_key,
                insecure=insecure,
                ca_cert=ca_cert,
                fingerprint=fingerprint,
            )
        )
    except click.ClickException as e:
        print_error(str(e), color_opt=client.color)
        sys.exit(1)

    actual_daemon_id = status_data["daemon_id"]
    if expected_daemon_id and actual_daemon_id != expected_daemon_id:
        print_error(
            f"Daemon identity mismatch! Expected '{expected_daemon_id}' but found '{actual_daemon_id}'.",
            color_opt=client.color,
        )
        sys.exit(1)

    client.remotes.set_remote(
        name,
        url,
        actual_daemon_id,
        api_key,
        insecure=insecure,
        ca_cert=ca_cert,
        fingerprint=fingerprint,
    )
    print_success(f"Updated API key for remote '{name}'.", color_opt=client.color)


@command.command("status", short_help="Check connection and status of remote daemons.")
@click.argument("name", required=False, default=None)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def remote_status(client, name: Optional[str], json_output: bool, plain: bool):
    """Check connectivity, latency, version, and uptime for remote daemons."""
    client.remotes.ensure_local_remote()
    remotes = client.remotes.get_remotes()
    default_remote = client.remotes.get_default_remote()

    if not remotes:
        print_error("No remotes configured.", color_opt=client.color)
        sys.exit(1)

    if name:
        if name not in remotes:
            print_error(f"Remote '{name}' does not exist.", color_opt=client.color)
            sys.exit(1)
        targets = [(name, remotes[name], name == default_remote)]
    else:
        targets = [(r_name, remotes[r_name], r_name == default_remote) for r_name in sorted(remotes.keys())]

    async def _check_all():
        tasks = [check_single_remote_status(t_name, t_data, t_def) for t_name, t_data, t_def in targets]
        return await asyncio.gather(*tasks)

    results = run_coroutine(_check_all())

    if json_output:
        print_json(results if not name else results[0])
        return

    use_color = should_use_color(client.color) and not plain and not client.plain
    console = get_console(client.color)

    if not use_color:
        rows = []
        for r in results:
            prefix = "*" if r["is_default"] else " "
            latency = f"{r['latency_ms']}ms" if r["latency_ms"] is not None else "-"
            version = r["version"] or "-"
            uptime = r["uptime_formatted"] or "-"
            torrents = str(r["num_torrents"]) if r["num_torrents"] is not None else "-"
            rows.append([prefix, r["name"], r["status"], latency, r["url"], version, uptime, torrents])
        headers = ["", "Name", "Status", "Latency", "URL", "Version", "Uptime", "Torrents"]
        click.echo(tabulate(rows, headers=headers, tablefmt="plain"))
        return

    has_default = any(r["is_default"] for r in results)
    theme = getattr(client, "theme", "modern")
    table = Table(
        box=get_box_style(theme),
        border_style=get_border_style(theme),
        header_style="bold cyan",
        caption="[green]*[/green] default remote" if has_default else None,
        caption_style="none",
    )
    table.add_column("", justify="center", width=1)
    table.add_column("Name", style="bold", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Latency", justify="right", no_wrap=True)
    table.add_column("URL", min_width=24, no_wrap=False)
    table.add_column("Version", no_wrap=True)
    table.add_column("Uptime", no_wrap=True)
    table.add_column("Torrents", justify="right", no_wrap=True)

    for r in results:
        marker = "[green]*[/green]" if r["is_default"] else " "
        status_str = r["status"]
        if status_str == "online":
            status_display = "[green]● online[/green]"
        elif status_str == "auth_failed":
            status_display = "[yellow]● auth_failed[/yellow]"
        elif status_str == "id_mismatch":
            status_display = "[bold red]✖ id_mismatch[/bold red]"
        else:
            status_display = "[red]● offline[/red]"

        latency_str = format_latency(r["latency_ms"], use_color=True)
        version_str = escape(r["version"] or "-")
        uptime_str = escape(r["uptime_formatted"] or "-")
        torrents_str = str(r["num_torrents"]) if r["num_torrents"] is not None else "-"

        table.add_row(
            marker,
            escape(r["name"]),
            status_display,
            latency_str,
            escape(r["url"]),
            version_str,
            uptime_str,
            torrents_str,
        )

    console.print(table)


@command.command("list", short_help="List configured remotes.")
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def remote_list(client, json_output: bool, plain: bool):
    """List configured remotes."""
    client.remotes.ensure_local_remote()
    remotes = client.remotes.get_remotes()
    default_remote = client.remotes.get_default_remote()

    items = []
    for r_name in sorted(remotes.keys()):
        r_info = remotes[r_name]
        is_def = (r_name == default_remote)
        items.append({
            "name": r_name,
            "url": r_info.get("url", ""),
            "daemon_id": r_info.get("daemon_id", ""),
            "is_default": is_def,
        })

    if json_output:
        print_json(items)
        return

    use_color = should_use_color(client.color) and not plain and not client.plain
    console = get_console(client.color)

    if not use_color:
        table_rows = []
        for item in items:
            prefix = "*" if item["is_default"] else " "
            table_rows.append([prefix, item["name"], item["url"], item["daemon_id"]])
        headers = ["", "Name", "URL", "Daemon ID"]
        click.echo(tabulate(table_rows, headers=headers, tablefmt="plain"))
        return

    has_default = any(item["is_default"] for item in items)
    theme = getattr(client, "theme", "modern")
    table = Table(
        box=get_box_style(theme),
        border_style=get_border_style(theme),
        header_style="bold cyan",
        caption="[green]*[/green] default remote" if has_default else None,
        caption_style="none",
    )
    table.add_column("", justify="center", width=1)
    table.add_column("Name", style="bold", no_wrap=True)
    table.add_column("URL", no_wrap=False)
    table.add_column("Daemon ID", no_wrap=True)

    for item in items:
        marker = "[green]*[/green]" if item["is_default"] else " "
        table.add_row(
            marker,
            escape(item["name"]),
            escape(item["url"]),
            escape(item["daemon_id"]),
        )

    console.print(table)


@command.command("use", short_help="Switch the active default remote.")
@click.argument("name")
@click.pass_obj
def remote_use(client, name: str):
    """Switch the default remote."""
    client.remotes.ensure_local_remote()
    if not client.remotes.get_remote(name):
        print_error(f"Remote '{name}' does not exist.", color_opt=client.color)
        sys.exit(1)

    client.remotes.set_default_remote(name)
    print_success(f"Switched default remote to '{name}'.", color_opt=client.color)


@command.command("remove", short_help="Remove a remote.")
@click.argument("name")
@click.pass_obj
def remote_remove(client, name: str):
    """Remove a configured remote."""
    client.remotes.ensure_local_remote()
    if not client.remotes.remove_remote(name):
        print_error(f"Remote '{name}' does not exist.", color_opt=client.color)
        sys.exit(1)

    print_success(f"Removed remote '{name}'.", color_opt=client.color)


@command.command("show", short_help="Show details for a remote.")
@click.argument("name")
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def remote_show(client, name: str, json_output: bool, plain: bool):
    """Show details for a remote."""
    client.remotes.ensure_local_remote()
    remote_data = client.remotes.get_remote(name)
    if not remote_data:
        print_error(f"Remote '{name}' does not exist.", color_opt=client.color)
        sys.exit(1)

    default_remote = client.remotes.get_default_remote()
    raw_key = remote_data.get("key", "")
    masked_key = f"{raw_key[:13]}..." if len(raw_key) > 13 else ("(set)" if raw_key else "(none)")

    info = {
        "name": name,
        "url": remote_data.get("url", ""),
        "daemon_id": remote_data.get("daemon_id", ""),
        "is_default": (name == default_remote),
        "key_prefix": masked_key,
    }

    if json_output:
        print_json(info)
        return

    use_color = should_use_color(client.color) and not plain and not client.plain
    console = get_console(client.color)

    rows = [
        ("Name", info["name"]),
        ("URL", info["url"]),
        ("Daemon ID", info["daemon_id"]),
        ("Default", info["is_default"]),
        ("API Key", info["key_prefix"]),
    ]

    if not use_color:
        table_rows = [
            (k, ("Yes" if v else "No") if isinstance(v, bool) else str(v))
            for k, v in rows
        ]
        click.echo(tabulate(table_rows, headers=["Property", "Value"], tablefmt="plain"))
        return

    render_kv_table(
        console,
        rows,
        title=f"Remote: {name}",
        key_header="Property",
        value_header="Value",
        num_columns=1,
    )
