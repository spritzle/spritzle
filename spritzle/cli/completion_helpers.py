#
# spritzle/cli/completion_helpers.py
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
import concurrent.futures
from typing import Any, List, Optional

import click
from click.shell_completion import CompletionItem

TORRENT_FLAGS = (
    "apply_ip_filter",
    "auto_managed",
    "default_dont_download",
    "disable_dht",
    "disable_lsd",
    "disable_pex",
    "duplicate_is_error",
    "no_verify_files",
    "override_trackers",
    "override_web_seeds",
    "paused",
    "seed_mode",
    "sequential_download",
    "share_mode",
    "stop_when_ready",
    "super_seeding",
    "update_subscribe",
    "upload_mode",
)


def complete_torrent_flags(
    ctx: Optional[click.Context], param: Any, incomplete: str
) -> List[CompletionItem]:
    """Complete libtorrent flag names."""
    return [
        CompletionItem(flag)
        for flag in TORRENT_FLAGS
        if flag.startswith(incomplete)
    ]


def complete_remotes(
    ctx: Optional[click.Context], param: Any, incomplete: str
) -> List[CompletionItem]:
    """Complete configured remote profile names."""
    try:
        config_dir = None
        cur = ctx
        while cur:
            if cur.params and cur.params.get("config"):
                config_dir = cur.params["config"]
                break
            cur = cur.parent

        from spritzle.cli.config import RemotesConfig

        remotes_cfg = RemotesConfig(config_dir=config_dir)
        remotes_cfg.ensure_local_remote()
        remotes = remotes_cfg.get_remotes()
        return [
            CompletionItem(name, help=info.get("url", ""))
            for name, info in remotes.items()
            if name.startswith(incomplete)
        ]
    except Exception:
        return []


def complete_torrent_identifiers(
    ctx: Optional[click.Context], param: Any, incomplete: str
) -> List[CompletionItem]:
    """Complete active torrent info-hashes and names via daemon API."""
    try:
        client = None
        if ctx and hasattr(ctx, "obj") and ctx.obj:
            client = ctx.obj
        else:
            config_dir = None
            remote = None
            cur = ctx
            while cur:
                if cur.params:
                    if not config_dir and cur.params.get("config"):
                        config_dir = cur.params["config"]
                    if not remote and cur.params.get("remote"):
                        remote = cur.params["remote"]
                cur = cur.parent

            from spritzle.cli.main import Client

            client = Client(config=config_dir, remote=remote)

        if not client.base_url and not client.token:
            return []

        import aiohttp

        async def _fetch():
            headers = {}
            if client.token:
                headers["Authorization"] = f"Bearer {client.token}"

            import ssl

            connector = None
            if client.insecure:
                connector = aiohttp.TCPConnector(ssl=False)
            elif client.fingerprint:
                fp_bytes = bytes.fromhex(client.fingerprint.replace(":", "").strip())
                connector = aiohttp.TCPConnector(ssl=aiohttp.Fingerprint(fp_bytes))
            elif client.ca_cert:
                ssl_ctx = ssl.create_default_context(cafile=client.ca_cert)
                connector = aiohttp.TCPConnector(ssl=ssl_ctx)

            timeout = aiohttp.ClientTimeout(total=0.5)
            url = client.url("torrent", "keys=name")
            async with aiohttp.ClientSession(
                headers=headers, timeout=timeout, connector=connector
            ) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return []

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                data = executor.submit(lambda: asyncio.run(_fetch())).result(timeout=0.6)
        else:
            data = asyncio.run(_fetch())

        if not isinstance(data, list):
            return []

        results: List[CompletionItem] = []
        inc_lower = incomplete.lower()
        for item in data:
            if not isinstance(item, dict):
                ih = str(item)
                name = ""
            else:
                ih = str(item.get("info_hash", ""))
                name = str(item.get("name", ""))

            if ih.lower().startswith(inc_lower):
                results.append(CompletionItem(ih, help=name or None))
            elif name and name.lower().startswith(inc_lower):
                results.append(CompletionItem(name, help=ih[:8] if ih else None))

        return results
    except Exception:
        return []


PROFILES = (
    "deluge-2.1.1",
    "qbittorrent-4.6.5",
    "transmission-4.0.5",
    "spritzle-default",
)


def complete_profiles(
    ctx: Optional[click.Context], param: Any, incomplete: str
) -> List[CompletionItem]:
    """Complete client identification profile names."""
    return [
        CompletionItem(p)
        for p in PROFILES
        if p.startswith(incomplete)
    ]
