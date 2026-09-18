#
# spritzle/cli/commands/stats.py
#
# Copyright (C) 2016-2026 Andrew Resch <andrewresch@gmail.com>
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
from typing import Any, Dict

import click
from rich import box
from rich.table import Table
from tabulate import tabulate

from spritzle.cli.display import (
    format_bytes,
    get_console,
    get_response_error,
    print_error,
    print_json,
    render_kv_table,
    should_use_color,
)


@click.command("stats", short_help="Show session statistics.")
@click.option("-a", "--all", "all_stats", is_flag=True, default=False, help="Show all raw session counters.")
@click.option("--raw", is_flag=True, default=False, help="Print raw unformatted numbers.")
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, all_stats, raw, json_output, plain):
    """Show session throughput, peer counts, and transfer statistics."""
    client.do_command(f, all_stats, raw, json_output, plain)


async def f(client, all_stats: bool = False, raw: bool = False, json_output: bool = False, plain: bool = False):
    color_opt = getattr(client, "color", None)
    async with client.session.get(client.url("session/stats")) as resp:
        if resp.status != 200:
            err_msg = await get_response_error(resp)
            print_error(f"Error fetching stats: {err_msg}", color_opt=color_opt)
            sys.exit(1)

        status: Dict[str, Any] = await resp.json()

    if all_stats:
        if json_output:
            print_json(status)
            return

        table = []
        for k, v in sorted(status.items()):
            table.append([k, v])

        if should_use_color(color_opt) and not plain:
            console = get_console(color_opt)
            render_kv_table(
                console,
                table,
                title="All Session Statistics",
                key_header="Statistic",
                value_header="Value",
            )
        else:
            print(tabulate(table, tablefmt="plain"))
        return

    # Curated dashboard summary
    recv_payload = int(status.get("net.recv_payload_bytes", 0))
    sent_payload = int(status.get("net.sent_payload_bytes", 0))
    recv_total = int(status.get("net.recv_bytes", 0))
    sent_total = int(status.get("net.sent_bytes", 0))
    wasted = int(status.get("net.recv_redundant_bytes", 0)) + int(status.get("net.recv_failed_bytes", 0))
    ratio = round(sent_payload / recv_payload, 2) if recv_payload > 0 else 0.0

    summary_data = {
        "torrents": {
            "downloading": int(status.get("ses.num_downloading_torrents", 0)),
            "seeding": int(status.get("ses.num_seeding_torrents", 0)),
            "checking": int(status.get("ses.num_checking_torrents", 0)),
            "stopped": int(status.get("ses.num_stopped_torrents", 0)),
            "queued_download": int(status.get("ses.num_queued_download_torrents", 0)),
            "queued_seed": int(status.get("ses.num_queued_seeding_torrents", 0)),
        },
        "transfer": {
            "downloaded": recv_payload if raw else format_bytes(recv_payload),
            "uploaded": sent_payload if raw else format_bytes(sent_payload),
            "total_received": recv_total if raw else format_bytes(recv_total),
            "total_sent": sent_total if raw else format_bytes(sent_total),
            "ratio": ratio,
            "wasted": wasted if raw else format_bytes(wasted),
        },
        "peers": {
            "connected": int(status.get("peer.num_peers_connected", 0)),
            "half_open": int(status.get("peer.num_peers_half_open", 0)),
            "connection_attempts": int(status.get("peer.connection_attempts", 0)),
            "incoming_connections": int(status.get("peer.incoming_connections", 0)),
        },
        "dht": {
            "nodes": int(status.get("dht.dht_nodes", 0)),
            "torrents": int(status.get("dht.dht_torrents", 0)),
        },
    }

    if json_output:
        print_json(summary_data)
        return

    plain_rows = [
        ["Torrents: Downloading", summary_data["torrents"]["downloading"]],
        ["Torrents: Seeding", summary_data["torrents"]["seeding"]],
        ["Torrents: Checking", summary_data["torrents"]["checking"]],
        ["Torrents: Stopped", summary_data["torrents"]["stopped"]],
        ["Torrents: Queued (DL)", summary_data["torrents"]["queued_download"]],
        ["Torrents: Queued (Seed)", summary_data["torrents"]["queued_seed"]],
        ["Transfer: Downloaded", summary_data["transfer"]["downloaded"]],
        ["Transfer: Uploaded", summary_data["transfer"]["uploaded"]],
        ["Transfer: Total In", summary_data["transfer"]["total_received"]],
        ["Transfer: Total Out", summary_data["transfer"]["total_sent"]],
        ["Transfer: Ratio", str(ratio)],
        ["Transfer: Wasted", summary_data["transfer"]["wasted"]],
        ["Peers: Connected", summary_data["peers"]["connected"]],
        ["Peers: Half-Open", summary_data["peers"]["half_open"]],
        ["Peers: Attempts", summary_data["peers"]["connection_attempts"]],
        ["Peers: Incoming", summary_data["peers"]["incoming_connections"]],
        ["DHT: Nodes", summary_data["dht"]["nodes"]],
        ["DHT: Torrents", summary_data["dht"]["torrents"]],
    ]

    if plain or not should_use_color(color_opt):
        print(tabulate(plain_rows, tablefmt="plain"))
        return

    console = get_console(color_opt)
    table = Table(
        box=box.ROUNDED,
        title="Session Statistics Summary",
        title_style="bold",
        show_header=True,
    )
    table.add_column("Category", style="bold cyan", no_wrap=True)
    table.add_column("Metric")
    table.add_column("Value", style="bold")

    table.add_row("Torrents", "Downloading", str(summary_data["torrents"]["downloading"]))
    table.add_row("", "Seeding", str(summary_data["torrents"]["seeding"]))
    table.add_row("", "Checking", str(summary_data["torrents"]["checking"]))
    table.add_row("", "Stopped", str(summary_data["torrents"]["stopped"]))
    table.add_row("", "Queued (DL / Seed)", f"{summary_data['torrents']['queued_download']} / {summary_data['torrents']['queued_seed']}")
    table.add_section()
    table.add_row("Transfer", "Downloaded (Payload)", str(summary_data["transfer"]["downloaded"]))
    table.add_row("", "Uploaded (Payload)", str(summary_data["transfer"]["uploaded"]))
    table.add_row("", "Total (In / Out)", f"{summary_data['transfer']['total_received']} / {summary_data['transfer']['total_sent']}")
    table.add_row("", "Share Ratio", str(ratio))
    table.add_row("", "Wasted Data", str(summary_data["transfer"]["wasted"]))
    table.add_section()
    table.add_row("Peers", "Connected / Half-Open", f"{summary_data['peers']['connected']} / {summary_data['peers']['half_open']}")
    table.add_row("", "Attempts / Incoming", f"{summary_data['peers']['connection_attempts']} / {summary_data['peers']['incoming_connections']}")
    table.add_section()
    table.add_row("DHT", "Nodes / Torrents", f"{summary_data['dht']['nodes']} / {summary_data['dht']['torrents']}")

    console.print(table)
    console.print("[dim]Use 'spritzle stats --all' to view all 100+ raw internal counters.[/dim]")
