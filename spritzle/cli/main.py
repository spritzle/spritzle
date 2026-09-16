import asyncio
import importlib
import json
from pathlib import Path
import pkgutil
import sys
from typing import Optional, Union

import aiohttp
import click

from spritzle.cli.config import CLIConfig

CONTEXT_SETTINGS = dict(auto_envvar_prefix="SPRITZLE")


class Client(object):
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        config: Union[Path, str, None] = None,
        token: Optional[str] = None,
        color: Optional[bool] = None,
    ):
        if config is None:
            self.config = Path(Path.home(), ".config", "spritzle")
        else:
            self.config = Path(config)

        self.cli_config = CLIConfig(config_dir=self.config)

        self.host = host if host is not None else str(self.cli_config.get("host", "127.0.0.1"))
        self.port = int(port if port is not None else self.cli_config.get("port", 8080))
        self.token = token if token is not None else str(self.cli_config.get("token", ""))
        self.color = color if color is not None else self.cli_config.get("color", None)
        self.plain = bool(self.cli_config.get("plain", False))

        if not self.token and Path(self.config, "tokens").exists():
            try:
                with Path(self.config, "tokens").open() as f:
                    d = json.load(f)
                    if isinstance(d, dict) and f"{self.host}:{self.port}" in d:
                        self.token = d[f"{self.host}:{self.port}"]
            except Exception:
                pass

        self.session = None

    def url(self, path: str, query: str = "") -> str:
        path = path.lstrip("/")
        host = self.host
        if ":" in host and not (host.startswith("[") and host.endswith("]")):
            host = f"[{host}]"
        if query:
            return f"http://{host}:{self.port}/{path}?{query}"
        return f"http://{host}:{self.port}/{path}"

    def do_command(self, cmd, *args, **kwargs):
        async def _do_command(cmd, *args, **kwargs):
            headers = {"Authorization": self.token}
            async with aiohttp.ClientSession(headers=headers) as session:
                self.session = session
                await cmd(self, *args, **kwargs)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_do_command(cmd, *args, **kwargs))
        except aiohttp.ClientConnectorError:
            from spritzle.cli.display import print_error

            print_error(
                f"Could not connect to spritzled at {self.url('')}. Is the daemon running? (Run 'spritzled' to start it).",
                color_opt=self.color,
            )
            sys.exit(1)




cmd_dir = Path(__file__).parent / "commands"


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    "-c",
    "--config",
    default=None,
    help="Configuration directory. [default: ~/.config/spritzle]",
)
@click.option("-h", "--host", default=None, help="Daemon host. [default: 127.0.0.1]")
@click.option("-p", "--port", default=None, type=int, help="Daemon port. [default: 8080]")
@click.option("-t", "--token", default=None, help="Authentication token.")
@click.option("--color/--no-color", default=None, help="Enable or disable color output.")
@click.pass_context
def cli(ctx, config, host, port, token, color):
    """Command-line interface for Spritzle."""
    ctx.obj = Client(host=host, port=port, config=config, token=token, color=color)


def load_commands():
    """Adds all commands found in 'commands' subdirectory."""
    for module_info in pkgutil.iter_modules([cmd_dir]):
        try:
            mod = importlib.import_module("spritzle.cli.commands." + module_info.name)
        except ImportError as e:
            click.echo(e, file=sys.stderr)
        else:
            cmd = mod.command
            cmd_name = getattr(cmd, "name", None) or module_info.name.replace("_", "-")
            cli.add_command(cmd, name=cmd_name)


load_commands()


if __name__ == "__main__":
    cli()
