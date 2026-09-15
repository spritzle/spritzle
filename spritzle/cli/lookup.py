import re
import sys
from typing import Dict, List, Optional, Sequence

import click
from tabulate import tabulate


HEX_40_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def parse_query_params(query: Optional[Sequence[str]]) -> Dict[str, str]:
    """Parse query strings of format key=value into a dictionary."""
    params: Dict[str, str] = {}
    if not query:
        return params
    for q in query:
        if "=" in q:
            k, v = q.split("=", 1)
            params[k] = v
        else:
            params[q] = ""
    return params


async def resolve_target_torrents(
    client,
    torrent: Optional[str] = None,
    query: Optional[Sequence[str]] = None,
    all_torrents: bool = False,
) -> List[str]:
    """
    Resolves target torrents to a list of canonical info-hashes based on:
    - all_torrents: matches all torrents in the session
    - query: matches torrents filtering by query parameters
    - torrent: matches by exact info-hash, exact name, or partial name

    Exits with code 1 if a single torrent specification is ambiguous or not found.
    """
    if all_torrents:
        async with client.session.get(client.url("torrent")) as resp:
            if resp.status != 200:
                click.echo(
                    f"Error querying torrents: {resp.status} {resp.reason}",
                    file=sys.stderr,
                )
                sys.exit(1)
            return await resp.json()

    if query:
        params = parse_query_params(query)
        async with client.session.get(client.url("torrent"), params=params) as resp:
            if resp.status != 200:
                click.echo(
                    f"Error querying torrents: {resp.status} {resp.reason}",
                    file=sys.stderr,
                )
                sys.exit(1)
            return await resp.json()

    if not torrent:
        click.echo("Error: Specify a torrent, --query, or --all.", file=sys.stderr)
        sys.exit(1)

    assert torrent is not None
    torrent = torrent.strip()

    # 1. Direct info-hash match
    if HEX_40_RE.match(torrent):
        info_hash = torrent.lower()
        async with client.session.get(client.url(f"torrent/{info_hash}")) as resp:
            if resp.status == 200:
                return [info_hash]

    # 2. Exact name match
    exact_pattern = f"^{re.escape(torrent)}$"
    async with client.session.get(
        client.url("torrent"), params={"name": exact_pattern}
    ) as resp:
        if resp.status != 200:
            click.echo(
                f"Error querying torrents: {resp.status} {resp.reason}",
                file=sys.stderr,
            )
            sys.exit(1)
        matches: List[str] = await resp.json()

    # 3. Substring match fallback if exact match yielded no results
    if not matches:
        async with client.session.get(
            client.url("torrent"), params={"name": f".*{re.escape(torrent)}"}
        ) as resp:
            if resp.status == 200:
                matches = await resp.json()

    if not matches:
        click.echo(f"Error: No torrent found matching '{torrent}'.", file=sys.stderr)
        sys.exit(1)

    if len(matches) == 1:
        return matches

    # Ambiguous: multiple matches found
    click.echo(
        f"Error: Multiple torrents match '{torrent}'. Please specify the info-hash:",
        file=sys.stderr,
    )
    table = []
    for ih in matches:
        async with client.session.get(client.url(f"torrent/{ih}")) as resp:
            if resp.status == 200:
                t = await resp.json()
                table.append([ih, t.get("name", "<unknown>"), t.get("state", "")])
            else:
                table.append([ih, "<unknown>", ""])
    if table:
        click.echo(
            tabulate(table, headers=["info_hash", "name", "state"], tablefmt="simple"),
            file=sys.stderr,
        )
    sys.exit(1)


async def resolve_single_torrent(client, torrent: str) -> str:
    """Convenience helper to resolve a single torrent identifier to its info-hash."""
    results = await resolve_target_torrents(client, torrent=torrent)
    return results[0]
