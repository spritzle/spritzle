import sys

import click
from tabulate import tabulate


from spritzle.cli.display import (
    format_bytes,
    format_datetime,
    format_progress,
    format_speed,
    format_state,
    get_console,
    print_error,
    print_json,
    render_info_card,
    should_use_color,
)
from spritzle.cli.completion_helpers import complete_torrent_identifiers
from spritzle.cli.lookup import resolve_single_torrent


@click.command("info", short_help="Show detailed information for a torrent.")
@click.argument("torrent", required=True, shell_complete=complete_torrent_identifiers)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, torrent: str, json_output: bool, plain: bool):
    """Display comprehensive status and metadata for a specific torrent."""
    client.do_command(f, torrent, json_output, plain)


async def f(client, torrent: str, json_output: bool = False, plain: bool = False):
    info_hash = await resolve_single_torrent(client, torrent)
    async with client.session.get(client.url(f"torrent/{info_hash}?detail=full")) as resp:
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

    # Fallback to querying sub-resources if missing from daemon response
    if "files" not in data or "peers" not in data or "trackers" not in data:
        try:
            async with client.session.get(client.url(f"torrent/{info_hash}/files")) as f_resp:
                if f_resp.status == 200:
                    data["files"] = await f_resp.json()
        except Exception:
            pass
        try:
            async with client.session.get(client.url(f"torrent/{info_hash}/peers")) as p_resp:
                if p_resp.status == 200:
                    data["peers"] = await p_resp.json()
        except Exception:
            pass
        try:
            async with client.session.get(client.url(f"torrent/{info_hash}/trackers")) as t_resp:
                if t_resp.status == 200:
                    data["trackers"] = await t_resp.json()
        except Exception:
            pass

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

    added_time = data.get("added_time")
    added_str = format_datetime(added_time)
    completed_time = data.get("completed_time")
    completed_str = (
        format_datetime(completed_time)
        if completed_time and float(completed_time) > 0
        else None
    )

    total_up = float(data.get("all_time_upload") or data.get("total_upload") or 0)
    total_dl = float(data.get("all_time_download") or data.get("total_done") or data.get("total_download") or 0)
    ratio = (total_up / total_dl) if total_dl > 0 else 0.0

    total_pieces = data.get("total_pieces")
    piece_length = data.get("piece_length")
    if total_pieces:
        pieces_disp = f"{num_pieces} / {total_pieces}"
        if piece_length:
            pieces_disp += f" ({format_bytes(piece_length, human=False)})"
    else:
        pieces_disp = str(num_pieces)

    items = [
        ("Name", name),
        ("Info Hash", info_hash),
        ("State", state_str),
        ("Progress", format_progress(progress, human=False)),
        ("Download Rate", format_speed(dl_rate, human=False)),
        ("Upload Rate", format_speed(ul_rate, human=False)),
        ("Share Ratio", f"{ratio:.2f}"),
        ("Total Size", format_bytes(total_size, human=False)),
        ("Downloaded", format_bytes(total_done, human=False)),
        ("Wanted Size", format_bytes(total_wanted, human=False)),
        ("Peers", f"{num_peers} (seeds: {num_seeds})"),
        ("Pieces", pieces_disp),
    ]

    if added_str != "--":
        items.append(("Added", added_str))
    if completed_str:
        items.append(("Completed", completed_str))

    items.extend([
        ("Save Path", save_path),
        ("Tags", tags_str),
    ])

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

    trackers = data.get("trackers") or []
    if trackers:
        print()
        print("Trackers:")
        tracker_rows = []
        for tr in trackers:
            tier_str = str(tr.get("tier", 0))
            url_str = str(tr.get("url", ""))
            if tr.get("updating"):
                st_str = "updating"
            elif tr.get("fails", 0) > 0 or (tr.get("last_error") and tr["last_error"].get("value", 0) != 0):
                st_str = tr.get("message") or (tr.get("last_error") or {}).get("message") or f"error ({tr.get('fails')} fails)"
            elif tr.get("verified") or tr.get("is_working"):
                st_str = "working"
            else:
                st_str = "idle"
            tracker_rows.append([tier_str, url_str, st_str])
        print(tabulate(tracker_rows, headers=["Tier", "URL", "Status"], tablefmt="plain"))

    peers = data.get("peers") or []
    if peers:
        print()
        print(f"Connected Peers ({len(peers)}):")
        peer_rows = []
        for p in peers:
            peer_rows.append([
                str(p.get("ip", "")),
                str(p.get("client") or "<unknown>").strip() or "<unknown>",
                format_speed(p.get("down_speed", 0), human=False),
                format_speed(p.get("up_speed", 0), human=False),
                format_progress(p.get("progress", 0.0), human=False),
            ])
        print(tabulate(peer_rows, headers=["IP", "Client", "Down Rate", "Up Rate", "Progress"], tablefmt="plain"))

    files = data.get("files") or []
    if files:
        print()
        print(f"Files ({len(files)}):")
        file_rows = []
        for f in files:
            file_rows.append([
                str(f.get("index", 0)),
                format_progress(f.get("progress", 0.0), human=False),
                format_bytes(f.get("size", 0), human=False),
                str(f.get("path", "")),
            ])
        print(tabulate(file_rows, headers=["#", "Progress", "Size", "Path"], tablefmt="plain"))
