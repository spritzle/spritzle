import sys
from typing import Dict, List, Optional

import click

from spritzle.cli.display import get_console, print_error, should_use_color

EXAMPLES: Dict[str, List[str]] = {
    "add": [
        "spritzle add /path/to/file.torrent",
        "spritzle add http://example.com/file.torrent",
        "spritzle add <info-hash>",
        "spritzle add -t linux -t iso /path/to/file.torrent",
        "spritzle add -o save_path=/mnt/downloads /path/to/file.torrent",
        "spritzle add -Q /path/to/file.torrent",
    ],
    "list": [
        "spritzle list",
        "spritzle list -q name=archlinux.*",
        "spritzle list -q state=downloading",
        "spritzle list -f name,state,progress,download_rate",
        "spritzle list --json",
        "spritzle list --plain",
    ],
    "pause": [
        "spritzle pause archlinux-x86_64.iso",
        "spritzle pause d3b07384d113edec49eaa6238ad5ff00fc7b0553",
        "spritzle pause -q name=archlinux.*",
        "spritzle pause --all",
        "spritzle pause -Q --all",
    ],
    "resume": [
        "spritzle resume archlinux-x86_64.iso",
        "spritzle resume d3b07384d113edec49eaa6238ad5ff00fc7b0553",
        "spritzle resume -q name=archlinux.*",
        "spritzle resume --all",
    ],
    "remove": [
        "spritzle remove archlinux-x86_64.iso",
        "spritzle remove --delete-files archlinux-x86_64.iso",
        "spritzle remove -q name=test.*",
        "spritzle remove --all",
    ],
    "flags": [
        "spritzle flags archlinux-x86_64.iso",
        "spritzle flags archlinux-x86_64.iso -s auto_managed",
        "spritzle flags -q name=archlinux.* -u auto_managed",
        "spritzle flags archlinux-x86_64.iso --json",
    ],
    "move_storage": [
        "spritzle move_storage archlinux-x86_64.iso /mnt/storage",
        "spritzle move_storage d3b07384d113edec49eaa6238ad5ff00fc7b0553 /mnt/storage",
    ],
    "stats": [
        "spritzle stats",
        "spritzle stats --json",
        "spritzle stats --plain",
    ],
    "settings": [
        "spritzle settings",
        "spritzle settings -s download_rate_limit 1048576",
        "spritzle settings -s enable_dht false",
        "spritzle settings --json",
    ],
    "config": [
        "spritzle config",
        "spritzle config -s auth_timeout 3600",
        "spritzle config --json",
    ],
    "auth": [
        "spritzle auth",
        "spritzle auth --password secret",
    ],
}


@click.command("help", short_help="Show help and examples for commands.")
@click.argument("command_name", required=False, metavar="[COMMAND]")
@click.pass_context
def command(ctx, command_name: Optional[str] = None):
    """Show help and usage examples for Spritzle commands."""
    root_ctx = ctx.parent or ctx
    root_cmd = root_ctx.command

    if not command_name:
        click.echo(root_cmd.get_help(root_ctx))
        click.echo("\nTip: Run 'spritzle help <command>' for command-specific options and examples.")
        return

    sub_cmd = getattr(root_cmd, "get_command", lambda c, n: None)(root_ctx, command_name)
    if not sub_cmd:
        print_error(f"No such command '{command_name}'.", color_opt=getattr(root_ctx.obj, "color", None))
        click.echo("\nRun 'spritzle help' to see all available commands.", file=sys.stderr)
        sys.exit(1)

    sub_ctx = click.Context(sub_cmd, info_name=command_name, parent=root_ctx)
    help_text = sub_cmd.get_help(sub_ctx)
    click.echo(help_text)

    examples = EXAMPLES.get(command_name)
    if examples:
        is_color = should_use_color(getattr(root_ctx.obj, "color", None))
        if is_color:
            console = get_console(getattr(root_ctx.obj, "color", None))
            console.print("\n[bold cyan]Examples:[/bold cyan]")
            for ex in examples:
                console.print(f"  [green]$[/green] {ex}")
        else:
            click.echo("\nExamples:")
            for ex in examples:
                click.echo(f"  $ {ex}")
