#
# spritzle/cli/commands/daemon_config.py
#
# Copyright (C) 2016 Andrew Resch <andrewresch@gmail.com>
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

import json
import sys

import click
from tabulate import tabulate

from spritzle.cli.display import (
    get_console,
    print_error,
    print_json,
    render_kv_table,
    should_use_color,
)


@click.command("daemon-config", short_help="Show and modify config of the daemon.")
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.option(
    "--set",
    "-s",
    "set_value",
    type=str,
    nargs=2,
    multiple=True,
    help="Set a config value as: key value",
)
@click.option(
    "--reload",
    "-r",
    "do_reload",
    is_flag=True,
    default=False,
    help="Trigger the daemon to reload configuration from disk.",
)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, key, value, set_value, do_reload, json_output, plain):
    if do_reload or key == "reload":
        client.do_command(reloader, json_output, plain)
    elif key and value is not None:
        client.do_command(setter, [(key, value)])
    elif key and not set_value:
        client.do_command(show_single, key, json_output, plain)
    elif set_value:
        client.do_command(setter, set_value)
    else:
        client.do_command(show, json_output, plain)


async def reloader(client, json_output: bool = False, plain: bool = False):
    async with client.session.post(client.url("config/reload")) as resp:
        if resp.status != 200:
            err_msg = resp.reason
            try:
                err_json = await resp.json()
                err_msg = err_json.get("message") or err_json.get("reason") or err_msg
            except Exception:
                pass
            print_error(
                f"Error reloading config: HTTP {resp.status} ({err_msg})",
                color_opt=getattr(client, "color", None),
            )
            sys.exit(1)

        result = await resp.json()

    if json_output:
        print_json(result)
        return

    reloaded = result.get("reloaded", False)
    if reloaded:
        msg = "Daemon configuration reloaded successfully."
    else:
        msg = "Daemon configuration checked; no changes detected."

    if should_use_color(getattr(client, "color", None)) and not plain:
        console = get_console(getattr(client, "color", None))
        symbol = "[bold green]✓[/bold green]" if reloaded else "[bold yellow]•[/bold yellow]"
        console.print(f"{symbol} {msg}")
    else:
        print(msg)


async def setter(client, set_value):
    d = {}
    for k, v in set_value:
        try:
            d[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError, ValueError):
            d[k] = v
    async with client.session.patch(client.url("config"), json=d) as resp:
        if resp.status != 200:
            err_msg = resp.reason
            try:
                err_json = await resp.json()
                err_msg = err_json.get("message") or err_json.get("reason") or err_msg
            except Exception:
                pass
            print_error(
                f"Error updating config: HTTP {resp.status} ({err_msg})",
                color_opt=getattr(client, "color", None),
            )
            sys.exit(1)


async def show_single(client, key: str, json_output: bool = False, plain: bool = False):
    async with client.session.get(client.url("config")) as resp:
        if resp.status != 200:
            err_msg = resp.reason
            try:
                err_json = await resp.json()
                err_msg = err_json.get("message") or err_json.get("reason") or err_msg
            except Exception:
                pass
            print_error(
                f"Error fetching config: HTTP {resp.status} ({err_msg})",
                color_opt=getattr(client, "color", None),
            )
            sys.exit(1)

        config = await resp.json()

    if key not in config:
        print_error(
            f"Config key '{key}' not found.",
            color_opt=getattr(client, "color", None),
        )
        sys.exit(1)

    val = config[key]
    if json_output:
        print_json({key: val})
        return

    if should_use_color(getattr(client, "color", None)) and not plain:
        console = get_console(getattr(client, "color", None))
        render_kv_table(
            console,
            [(key, val)],
            title="Spritzle Daemon Configuration",
            key_header="Option",
            value_header="Value",
            theme=getattr(client, "theme", "modern"),
        )
    else:
        print(tabulate([[key, val]], tablefmt="plain"))


async def show(client, json_output=False, plain=False):
    async with client.session.get(client.url("config")) as resp:
        if resp.status != 200:
            err_msg = resp.reason
            try:
                err_json = await resp.json()
                err_msg = err_json.get("message") or err_json.get("reason") or err_msg
            except Exception:
                pass
            print_error(
                f"Error fetching config: HTTP {resp.status} ({err_msg})",
                color_opt=getattr(client, "color", None),
            )
            sys.exit(1)

        config = await resp.json()

    if json_output:
        print_json(config)
        return

    table = [(k, v) for k, v in sorted(config.items())]

    if should_use_color(getattr(client, "color", None)) and not plain:
        console = get_console(getattr(client, "color", None))
        render_kv_table(
            console,
            table,
            title="Spritzle Daemon Configuration",
            key_header="Option",
            value_header="Value",
            theme=getattr(client, "theme", "modern"),
        )
    else:
        print(tabulate(table, tablefmt="plain"))
