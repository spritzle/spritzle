import sys

import click
from rich.table import Table
from tabulate import tabulate

from spritzle.cli.completion_helpers import complete_torrent_identifiers
from spritzle.cli.display import (
    get_border_style,
    get_box_style,
    get_console,
    get_response_error,
    print_error,
    print_json,
    print_success,
    should_use_color,
)
from spritzle.cli.lookup import resolve_single_torrent


@click.command("trackers", short_help="Show and manage trackers for a torrent.")
@click.argument(
    "torrent",
    required=False,
    metavar="[INFO-HASH|NAME]",
    shell_complete=complete_torrent_identifiers,
)
@click.option(
    "-a",
    "--add",
    "add_url",
    type=str,
    default=None,
    help="Add a tracker URL.",
)
@click.option(
    "-t",
    "--tier",
    "tier",
    type=int,
    default=0,
    help="Tier for newly added tracker (default: 0).",
)
@click.option(
    "-d",
    "--remove",
    "--delete",
    "remove_target",
    type=str,
    default=None,
    help="Remove a tracker by URL or index.",
)
@click.option(
    "-r",
    "--reannounce",
    "reannounce",
    is_flag=True,
    default=False,
    help="Force an immediate tracker re-announce.",
)
@click.option("--header/--no-header", default=True, help="Print header in output.")
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(
    client,
    torrent,
    add_url,
    tier,
    remove_target,
    reannounce,
    header,
    json_output,
    plain,
):
    if add_url or remove_target or reannounce:
        client.do_command(
            manager,
            torrent=torrent,
            add_url=add_url,
            tier=tier,
            remove_target=remove_target,
            reannounce=reannounce,
        )
    else:
        client.do_command(
            show,
            torrent=torrent,
            header=header,
            json_output=json_output,
            plain=plain,
        )


async def manager(client, torrent, add_url, tier, remove_target, reannounce, **kwargs):
    if not torrent:
        print_error("Specify a torrent to manage trackers.", color_opt=getattr(client, "color", None))
        sys.exit(1)

    info_hash = await resolve_single_torrent(client, torrent)

    if add_url:
        payload = {"url": add_url, "tier": tier}
        async with client.session.post(
            client.url(f"torrent/{info_hash}/trackers"), json=payload
        ) as resp:
            if resp.status not in (200, 201):
                err = await get_response_error(resp)
                print_error(f"Error adding tracker: {err}", color_opt=getattr(client, "color", None))
                sys.exit(1)
            print_success(f"Added tracker {add_url} (tier {tier}) to {torrent}.", color_opt=getattr(client, "color", None))

    if remove_target:
        params = {}
        if remove_target.isdigit():
            params["index"] = remove_target
        else:
            params["url"] = remove_target

        async with client.session.delete(
            client.url(f"torrent/{info_hash}/trackers"), params=params
        ) as resp:
            if resp.status != 200:
                err = await get_response_error(resp)
                print_error(f"Error removing tracker: {err}", color_opt=getattr(client, "color", None))
                sys.exit(1)
            print_success(f"Removed tracker {remove_target} from {torrent}.", color_opt=getattr(client, "color", None))

    if reannounce:
        async with client.session.post(
            client.url(f"torrent/{info_hash}/reannounce")
        ) as resp:
            if resp.status != 200:
                err = await get_response_error(resp)
                print_error(f"Error reannouncing {torrent}: {err}", color_opt=getattr(client, "color", None))
                sys.exit(1)
            print_success(f"Reannounced {torrent} to all trackers.", color_opt=getattr(client, "color", None))


async def show(client, torrent, header=True, json_output=False, plain=False, **kwargs):
    if not torrent:
        print_error("Specify a torrent to view trackers.", color_opt=getattr(client, "color", None))
        sys.exit(1)

    info_hash = await resolve_single_torrent(client, torrent)

    async with client.session.get(client.url(f"torrent/{info_hash}/trackers")) as resp:
        if resp.status != 200:
            err = await get_response_error(resp)
            print_error(f"Error getting trackers for {torrent}: {err}", color_opt=getattr(client, "color", None))
            sys.exit(1)
        trackers = await resp.json()

    if json_output:
        print_json(trackers)
        return

    is_interactive = should_use_color(getattr(client, "color", None)) and not plain

    if is_interactive:
        console = get_console(getattr(client, "color", None))
        theme = getattr(client, "theme", "modern")
        table = Table(
            box=get_box_style(theme),
            border_style=get_border_style(theme),
            show_header=header,
            caption_style="none",
            header_style="bold cyan",
        )
        table.add_column("Tier", justify="right", style="dim", no_wrap=True)
        table.add_column("URL", justify="left")
        table.add_column("Status", justify="left", no_wrap=True)
        table.add_column("Fails", justify="right", no_wrap=True)
        table.add_column("Next Announce", justify="right", no_wrap=True)
        table.add_column("Message", justify="left")

        for tr in trackers:
            tier_str = str(tr.get("tier", 0))
            url_str = str(tr.get("url", ""))
            updating = tr.get("updating", False)
            fails = tr.get("fails", 0)
            message = str(tr.get("message", "") or "")
            next_announce = tr.get("next_announce")
            next_str = f"{next_announce}s" if next_announce is not None else "-"

            if updating:
                status_str = "[yellow]updating[/yellow]"
            elif fails > 0:
                status_str = f"[red]error ({fails})[/red]"
            else:
                status_str = "[green]working[/green]"

            table.add_row(
                tier_str,
                url_str,
                status_str,
                str(fails),
                next_str,
                message,
            )

        console.print(table)
    else:
        headers = ["Tier", "URL", "Status", "Fails", "Next Announce", "Message"] if header else []
        rows = []
        for tr in trackers:
            updating = tr.get("updating", False)
            fails = tr.get("fails", 0)
            if updating:
                st = "updating"
            elif fails > 0:
                st = f"error ({fails})"
            else:
                st = "working"
            next_ann = tr.get("next_announce")
            rows.append([
                tr.get("tier", 0),
                tr.get("url", ""),
                st,
                fails,
                f"{next_ann}s" if next_ann is not None else "-",
                tr.get("message", "") or "",
            ])
        click.echo(tabulate(rows, headers=headers, tablefmt="plain"))
