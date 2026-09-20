import sys

import click
from tabulate import tabulate


from spritzle.cli.display import (
    format_bytes,
    format_progress,
    format_speed,
    format_state,
    get_console,
    print_error,
    print_json,
    render_info_card,
    should_use_color,
)
from spritzle.cli.lookup import resolve_single_torrent


@click.command("info", short_help="Show detailed information for a torrent.")
@click.argument("torrent", required=True)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, torrent: str, json_output: bool, plain: bool):
    """Display comprehensive status and metadata for a specific torrent."""
    client.do_command(f, torrent, json_output, plain)


async def f(client, torrent: str, json_output: bool = False, plain: bool = False):
    info_hash = await resolve_single_torrent(client, torrent)
    async with client.session.get(client.url(f"torrent/{info_hash}")) as resp:
        if resp.status != 200:
            err_msg = resp.reason
            try:
                err_json = await resp.json()
                err_msg = err_json.get("message") or err_json.get("reason") or err_msg
            except Exception:
                pass
            print_error(
                f"Error fetching torrent info: HTTP {resp.status} ({err_msg})",
                color_opt=getattr(client, "color", None),
            )
            sys.exit(1)
        data = await resp.json()

    if json_output:
        print_json(data)
        return

    use_color = should_use_color(getattr(client, "color", None)) and not plain
    color_opt = getattr(client, "color", None)
    theme = getattr(client, "theme", "modern")

    if use_color:
        console = get_console(color_opt)
        render_info_card(console, data, info_hash, color_opt=color_opt, theme=theme)
        return

    # Plain output mode
    name = data.get("name", "<unknown>")
    state = data.get("state", "")
    progress = data.get("progress", 0.0)
    dl_rate = data.get("download_rate", 0)
    ul_rate = data.get("upload_rate", 0)
    total_size = data.get("total_size", 0)
    total_done = data.get("total_done", 0)
    total_wanted = data.get("total_wanted", 0)
    num_peers = data.get("num_peers", 0)
    num_seeds = data.get("num_seeds", 0)
    num_pieces = data.get("num_pieces", 0)
    save_path = data.get("save_path", "")
    tags = data.get("spritzle.tags", [])
    if isinstance(tags, list):
        tags_str = ", ".join(tags) if tags else "<none>"
    else:
        tags_str = str(tags)

    state_str = format_state(state, use_color=False)

    items = [
        ("Name", name),
        ("Info Hash", info_hash),
        ("State", state_str),
        ("Progress", format_progress(progress, human=False)),
        ("Download Rate", format_speed(dl_rate, human=False)),
        ("Upload Rate", format_speed(ul_rate, human=False)),
        ("Total Size", format_bytes(total_size, human=False)),
        ("Downloaded", format_bytes(total_done, human=False)),
        ("Wanted Size", format_bytes(total_wanted, human=False)),
        ("Peers", f"{num_peers} (seeds: {num_seeds})"),
        ("Pieces", num_pieces),
        ("Save Path", save_path),
        ("Tags", tags_str),
    ]

    err_str = None
    if data.get("last_error"):
        err_str = str(data["last_error"])
    elif data.get("error"):
        err_val = data["error"]
        if isinstance(err_val, dict):
            if err_val.get("value", 0) != 0:
                err_str = err_val.get("message") or str(err_val)
        elif err_val:
            err_str = str(err_val)
    elif data.get("errc"):
        errc = data["errc"]
        if isinstance(errc, dict) and errc.get("value", 0) != 0:
            err_str = errc.get("message") or str(errc)
        elif isinstance(errc, int) and errc != 0:
            err_str = str(errc)

    if err_str:
        items.append(("Error", str(err_str)))

    print(tabulate(items, tablefmt="plain"))
