import sys
from typing import Dict, List, Optional

import click

from rich.table import Table

from spritzle.cli.display import BRAND_ACCENT, get_console, print_error, should_use_color

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
    "files": [
        "spritzle files archlinux-x86_64.iso",
        "spritzle files archlinux-x86_64.iso -p 0 7",
        "spritzle files archlinux-x86_64.iso --skip 1 --skip 2",
        "spritzle files archlinux-x86_64.iso --normal 0",
        "spritzle files archlinux-x86_64.iso --top 3",
        "spritzle files archlinux-x86_64.iso --all normal",
        "spritzle files archlinux-x86_64.iso --json",
        "spritzle files archlinux-x86_64.iso --plain",
    ],
    "trackers": [
        "spritzle trackers archlinux-x86_64.iso",
        "spritzle trackers archlinux-x86_64.iso --add http://tracker.example.com:6969/announce",
        "spritzle trackers archlinux-x86_64.iso --add http://backup.example.com/announce --tier 1",
        "spritzle trackers archlinux-x86_64.iso --remove http://tracker.example.com:6969/announce",
        "spritzle trackers archlinux-x86_64.iso --remove 0",
        "spritzle trackers archlinux-x86_64.iso --reannounce",
        "spritzle trackers archlinux-x86_64.iso --json",
    ],
    "reannounce": [
        "spritzle reannounce archlinux-x86_64.iso",
        "spritzle reannounce d3b07384d113edec49eaa6238ad5ff00fc7b0553",
        "spritzle reannounce -q name=archlinux.*",
        "spritzle reannounce --all",
    ],
    "settings": [
        "spritzle settings",
        "spritzle settings -s download_rate_limit 1048576",
        "spritzle settings -i tun0:6881",
        "spritzle settings --profile deluge-2.1.1",
        "spritzle settings --user-agent 'Deluge/2.1.1 libtorrent/2.0.10.0' --peer-id '-DE2110-'",
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
        "spritzle config theme",
        "spritzle config theme modern",
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
        "spritzle daemon-config --reload",
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
    is_color = should_use_color(getattr(root_ctx.obj, "color", None))

    if not command_name:
        if is_color:
            console = get_console(getattr(root_ctx.obj, "color", None))
            console.print(f"[bold {BRAND_ACCENT}]Spritzle[/bold {BRAND_ACCENT}] [dim]- Modern BitTorrent Client[/dim]\n")
            console.print(f"[bold]Usage:[/bold] [{BRAND_ACCENT}]spritzle[/{BRAND_ACCENT}] [dim][OPTIONS][/dim] [bold {BRAND_ACCENT}]COMMAND[/bold {BRAND_ACCENT}] [dim][ARGS]...[/dim]\n")

            opt_table = Table(box=None, padding=(0, 2), show_header=False)
            opt_table.add_column(style="green", no_wrap=True)
            opt_table.add_column(style="default")
            for param in root_cmd.params:
                opts = ", ".join(param.opts)
                if param.secondary_opts:
                    opts += " / " + ", ".join(param.secondary_opts)
                opt_table.add_row(opts, param.help or "")
            opt_table.add_row("--help", "Show this message and exit.")
            console.print(f"[bold {BRAND_ACCENT}]Options:[/bold {BRAND_ACCENT}]")
            console.print(opt_table)
            console.print("")

            cmd_table = Table(box=None, padding=(0, 2), show_header=False)
            cmd_table.add_column(style=f"bold {BRAND_ACCENT}", no_wrap=True)
            cmd_table.add_column(style="default")
            for name in sorted(root_cmd.list_commands(root_ctx)):
                sc = root_cmd.get_command(root_ctx, name)
                if sc and not sc.hidden:
                    cmd_table.add_row(name, sc.short_help or "")
            console.print(f"[bold {BRAND_ACCENT}]Commands:[/bold {BRAND_ACCENT}]")
            console.print(cmd_table)
            console.print("\n[dim]Tip: Run 'spritzle help <command>' for command-specific options and examples.[/dim]")
            return
        else:
            click.echo(root_cmd.get_help(root_ctx))
            click.echo("\nTip: Run 'spritzle help <command>' for command-specific options and examples.")
            return

    sub_cmd = getattr(root_cmd, "get_command", lambda c, n: None)(root_ctx, command_name)
    if not sub_cmd:
        print_error(f"No such command '{command_name}'.", color_opt=getattr(root_ctx.obj, "color", None))
        click.echo("\nRun 'spritzle help' to see all available commands.", file=sys.stderr)
        sys.exit(1)

    sub_ctx = click.Context(sub_cmd, info_name=command_name, parent=root_ctx)

    if is_color:
        console = get_console(getattr(root_ctx.obj, "color", None))
        args_str = " ".join(f"[{p.name.upper()}]" if not p.required else p.name.upper() for p in sub_cmd.params if isinstance(p, click.Argument))
        console.print(f"[bold]Usage:[/bold] [{BRAND_ACCENT}]spritzle {command_name}[/{BRAND_ACCENT}] [dim][OPTIONS][/dim] {args_str}".strip())
        if sub_cmd.help:
            console.print(f"\n  {sub_cmd.help.strip()}\n")
        elif sub_cmd.short_help:
            console.print(f"\n  {sub_cmd.short_help.strip()}\n")

        opts = [p for p in sub_cmd.params if isinstance(p, click.Option)]
        if opts:
            opt_table = Table(box=None, padding=(0, 2), show_header=False)
            opt_table.add_column(style="green", no_wrap=True)
            opt_table.add_column(style="default")
            for param in opts:
                o_str = ", ".join(param.opts)
                if param.secondary_opts:
                    o_str += " / " + ", ".join(param.secondary_opts)
                opt_table.add_row(o_str, param.help or "")
            opt_table.add_row("--help", "Show this message and exit.")
            console.print(f"[bold {BRAND_ACCENT}]Options:[/bold {BRAND_ACCENT}]")
            console.print(opt_table)
    else:
        help_text = sub_cmd.get_help(sub_ctx)
        click.echo(help_text)

    examples = EXAMPLES.get(command_name)
    if examples:
        if is_color:
            console = get_console(getattr(root_ctx.obj, "color", None))
            console.print(f"\n[bold {BRAND_ACCENT}]Examples:[/bold {BRAND_ACCENT}]")
            for ex in examples:
                console.print(f"  [green]$[/green] {ex}")
        else:
            click.echo("\nExamples:")
            for ex in examples:
                click.echo(f"  $ {ex}")
