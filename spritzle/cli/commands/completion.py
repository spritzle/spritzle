#
# spritzle/cli/commands/completion.py
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

import sys

import click
from click.shell_completion import get_completion_class


@click.command("completion", short_help="Generate shell completion script.")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False))
def command(shell: str):
    """Generate shell autocompletion script for bash, zsh, or fish.

    \b
    Examples:
      # Bash
      source <(spritzle completion bash)
      # Or persist to ~/.bashrc:
      spritzle completion bash >> ~/.bashrc

      # Zsh
      eval "$(spritzle completion zsh)"
      # Tip for Zsh: alias spritzle='noglob spritzle' to allow unquoted magnet links.

      # Fish
      spritzle completion fish | source
      # Or persist:
      spritzle completion fish > ~/.config/fish/completions/spritzle.fish
    """
    from spritzle.cli.main import cli

    cls = get_completion_class(shell.lower())
    if not cls:
        click.echo(f"Unsupported shell: {shell}", file=sys.stderr)
        sys.exit(1)

    assert cls is not None
    complete_obj = cls(cli, {}, "spritzle", "_SPRITZLE_COMPLETE")
    click.echo(complete_obj.source())
