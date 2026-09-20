import json
import sys

import click
from tabulate import tabulate

from spritzle.cli.display import (
    get_console,
    get_response_error,
    print_error,
    print_json,
    print_success,
    render_kv_table,
    should_use_color,
)


@click.command("settings", short_help="Show and modify settings of the session.")
@click.option(
    "--set",
    "-s",
    "set_value",
    type=str,
    nargs=2,
    multiple=True,
    help="Set a property value as: key value",
)
@click.option(
    "--reset",
    "-r",
    "reset_keys",
    type=str,
    multiple=True,
    help="Reset specified setting(s) to default value.",
)
@click.option(
    "--reset-all",
    is_flag=True,
    default=False,
    help="Reset all settings to default values.",
)
@click.option(
    "--modified",
    "-m",
    is_flag=True,
    default=False,
    help="Show only settings that differ from their default values.",
)
@click.option(
    "--defaults",
    "-d",
    is_flag=True,
    default=False,
    help="Show default values for settings.",
)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, set_value, reset_keys, reset_all, modified, defaults, json_output, plain):
    if set_value:
        client.do_command(setter, set_value)
    elif reset_keys or reset_all:
        client.do_command(resetter, reset_keys, reset_all)
    else:
        client.do_command(show, modified, defaults, json_output, plain)


async def setter(client, set_value):
    d = {}
    for k, v in set_value:
        try:
            d[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError, ValueError):
            d[k] = v
    headers = {"Content-Type": "application/json"}
    async with client.session.put(
        client.url("session/settings"), json=d, headers=headers
    ) as resp:
        if resp.status != 200:
            err_msg = await get_response_error(resp)
            print_error(f"Error setting properties: {err_msg}", getattr(client, "color", None))
            sys.exit(1)


async def resetter(client, reset_keys, reset_all):
    payload = {}
    if reset_all:
        payload["all"] = True
    else:
        payload["keys"] = list(reset_keys)

    headers = {"Content-Type": "application/json"}
    async with client.session.post(
        client.url("session/settings/reset"), json=payload, headers=headers
    ) as resp:
        if resp.status != 200:
            err = await get_response_error(resp)
            print_error(f"Error resetting settings: {err}", getattr(client, "color", None))
            sys.exit(1)

        result = await resp.json()
        reset_list = result.get("reset", [])
        if reset_all:
            print_success(
                f"Reset all {len(reset_list)} settings to default values.",
                getattr(client, "color", None),
            )
        else:
            print_success(
                f"Reset {len(reset_list)} setting(s) to default values: {', '.join(reset_list)}",
                getattr(client, "color", None),
            )


async def show(client, modified=False, defaults=False, json_output=False, plain=False):
    if defaults:
        async with client.session.get(client.url("session/settings/defaults")) as resp:
            if resp.status != 200:
                err_msg = await get_response_error(resp)
                print_error(f"Error getting default settings: {err_msg}", getattr(client, "color", None))
                sys.exit(1)
            display_data = await resp.json()
        title = "Session Settings (Defaults)"
        mod_keys = set()
    elif modified:
        async with client.session.get(
            client.url("session/settings"), params={"modified": "true"}
        ) as resp:
            if resp.status != 200:
                err_msg = await get_response_error(resp)
                print_error(f"Error getting settings: {err_msg}", getattr(client, "color", None))
                sys.exit(1)
            display_data = await resp.json()
        title = "Session Settings (Modified)"
        mod_keys = set(display_data.keys())
    else:
        async with client.session.get(client.url("session/settings")) as resp:
            if resp.status != 200:
                err_msg = await get_response_error(resp)
                print_error(f"Error getting settings: {err_msg}", getattr(client, "color", None))
                sys.exit(1)
            settings = await resp.json()

        async with client.session.get(client.url("session/settings/defaults")) as resp:
            if resp.status != 200:
                err_msg = await get_response_error(resp)
                print_error(f"Error getting default settings: {err_msg}", getattr(client, "color", None))
                sys.exit(1)
            default_settings = await resp.json()

        modified_keys = {
            k
            for k, v in settings.items()
            if k in default_settings and v != default_settings[k]
        }
        display_data = settings
        title = "Session Settings"
        mod_keys = modified_keys

    if json_output:
        print_json(display_data)
        return

    if modified and not display_data:
        click.echo("No settings have been modified from their default values.")
        return

    table = []
    for k, v in sorted(display_data.items()):
        table.append([k, v])

    if should_use_color(getattr(client, "color", None)) and not plain:
        console = get_console(getattr(client, "color", None))
        render_kv_table(
            console,
            table,
            title=title,
            key_header="Setting",
            value_header="Value",
            modified_keys=mod_keys,
            theme=getattr(client, "theme", "modern"),
        )
    else:
        print(tabulate(table, tablefmt="plain"))


