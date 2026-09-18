#
# spritzle/cli/commands/config.py
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

import click
from tabulate import tabulate

from spritzle.cli.config import coerce_config_value
from spritzle.cli.display import (
    get_console,
    print_error,
    print_json,
    print_success,
    render_kv_table,
    should_use_color,
)


@click.command("config", short_help="Show and modify local client configuration.")
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
    "--unset",
    "-u",
    "unset_keys",
    type=str,
    multiple=True,
    help="Unset a configuration override: key",
)
@click.option(
    "--reset",
    is_flag=True,
    default=False,
    help="Reset all CLI configuration to defaults.",
)
@click.option("--json", "json_output", is_flag=True, default=False, help="Output as JSON.")
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, key, value, set_value, unset_keys, reset, json_output, plain):
    config = client.cli_config

    if reset:
        config.reset()
        print_success("Reset CLI configuration to defaults.", color_opt=getattr(client, "color", None))
        return

    if unset_keys:
        for k in unset_keys:
            config.unset(k)
        return

    if key and value is not None:
        apply_set(config, [(key, value)])
    elif key and not set_value:
        show_single(client, key, json_output, plain)
    elif set_value:
        apply_set(config, set_value)
    else:
        show(client, json_output, plain)


def apply_set(config, set_value):
    try:
        for k, v in set_value:
            config[k] = coerce_config_value(v)
    except Exception as e:
        print_error(f"Error saving CLI configuration: {e}")
        sys.exit(1)


def show_single(client, key: str, json_output: bool = False, plain: bool = False):
    config = client.cli_config
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

    is_mod = {key} if config.is_modified(key) else set()
    if should_use_color(getattr(client, "color", None)) and not plain:
        console = get_console(getattr(client, "color", None))
        render_kv_table(
            console,
            [(key, val)],
            title="Spritzle Client Configuration",
            key_header="Option",
            value_header="Value",
            modified_keys=is_mod,
        )
    else:
        print(tabulate([[key, val]], tablefmt="plain"))


def show(client, json_output=False, plain=False):
    config = client.cli_config
    data = config.as_dict()

    if json_output:
        print_json(data)
        return

    table = [(k, data[k]) for k in sorted(data.keys())]
    modified_keys = {k for k in data if config.is_modified(k)}

    if should_use_color(getattr(client, "color", None)) and not plain:
        console = get_console(getattr(client, "color", None))
        render_kv_table(
            console,
            table,
            title="Spritzle Client Configuration",
            num_columns=1,
            key_header="Option",
            value_header="Value",
            modified_keys=modified_keys,
        )
    else:
        print(tabulate(table, tablefmt="plain"))
