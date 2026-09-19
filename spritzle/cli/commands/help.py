import sys
from typing import Dict, List, Optional

import click

from spritzle.cli.display import get_console, print_error, should_use_color

EXAMPLES: Dict[str, List[str]] = {
    "add": [
        "spritzle add /path/to/file.torrent",
        "spritzle add --watch archlinux-x86_64.iso.torrent",
        "spritzle add http://example.com/file.torrent",
        "spritzle add 'magnet:?xt=urn:btih:...'",
        "spritzle add <info-hash>",
        "spritzle add -t linux -t iso /path/to/file.torrent",
        "spritzle add -o save_path=/mnt/downloads /path/to/file.torrent",
        "spritzle add -Q /path/to/file.torrent",
        "echo 'magnet:?xt=urn:btih:...' | spritzle add -",
    ],
    "list": [
        "spritzle list",
        "spritzle list --watch",
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
    "move-storage": [
        "spritzle move-storage archlinux-x86_64.iso /mnt/storage",
        "spritzle move-storage d3b07384d113edec49eaa6238ad5ff00fc7b0553 /mnt/storage",
    ],
    "stats": [
        "spritzle stats",
        "spritzle stats --all",
        "spritzle stats --raw",
        "spritzle stats --json",
        "spritzle stats --plain",
    ],
    "status": [
        "spritzle status",
        "spritzle status --json",
        "spritzle status --plain",
    ],
    "completion": [
        "spritzle completion bash",
        "spritzle completion zsh",
        "spritzle completion fish",
        'eval "$(spritzle completion bash)"',
    ],
    "settings": [
        "spritzle settings",
        "spritzle settings -s download_rate_limit 1048576",
        "spritzle settings --modified",
        "spritzle settings --defaults",
        "spritzle settings --reset download_rate_limit",
        "spritzle settings --reset-all",
        "spritzle settings --json",
    ],
    "info": [
        "spritzle info archlinux-x86_64.iso",
        "spritzle info d3b07384d113edec49eaa6238ad5ff00fc7b0553",
        "spritzle info archlinux-x86_64.iso --json",
        "spritzle info archlinux-x86_64.iso --plain",
    ],
    "config": [
        "spritzle config",
        "spritzle config plain",
        "spritzle config plain true",
        "spritzle config -s color false",
        "spritzle config --unset plain",
        "spritzle config --reset",
        "spritzle config --json",
    ],
    "daemon-config": [
        "spritzle daemon-config",
        "spritzle daemon-config save_resume_data_interval",
        "spritzle daemon-config save_resume_data_interval 30",
        "spritzle daemon-config -s save_resume_data_interval 30",
        "spritzle daemon-config --json",
    ],
    "remote": [
        "spritzle remote list",
        "spritzle remote status",
        "spritzle remote add seedbox https://seedbox.example.com:17382 --key spritzle_8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c",
        "spritzle remote add local-nas https://192.168.1.50:17382 --key spritzle_... --insecure",
        "spritzle remote add local-nas https://192.168.1.50:17382 --key spritzle_... --ca-cert /path/to/ca.crt",
        "spritzle remote add local-nas https://192.168.1.50:17382 --key spritzle_... --fingerprint 2b490f05561a0f58dd713ae53b1b444b",
        "spritzle remote use seedbox",
        "spritzle remote show seedbox",
        "spritzle remote set-key seedbox",
        "spritzle remote remove seedbox",
        "spritzle remote status --json",
    ],
    "top": [
        "spritzle top",
        "spritzle top -i 0.5",
        "spritzle top -q state=downloading",
        "spritzle top --plain",
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
