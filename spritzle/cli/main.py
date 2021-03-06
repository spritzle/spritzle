import asyncio
import importlib
from pathlib import Path
import pkgutil
import sys

import aiohttp
import click
import yaml

CONTEXT_SETTINGS = dict(auto_envvar_prefix="SPRITZLE")


class Client(object):
    def __init__(self, host: str, port: int, config: str, token: str):
        self.host = host
        self.port = port
        self.config = Path(config)
        self.token = token

        if not token and Path(self.config, "tokens").exists():
            with Path(self.config, "tokens").open() as f:
                d = yaml.safe_load(f)
                if f"{host}:{port}" in d:
                    self.token = d[f"{host}:{port}"]

        self.session = None

    def url(self, path: str, query: str = "") -> str:
        return f"http://{self.host}:{self.port}/{path}?{query}"

    def do_command(self, cmd, *args, **kwargs):
        async def _do_command(cmd, *args, **kwargs):
            headers = {"Authorization": self.token}
            async with aiohttp.ClientSession(headers=headers) as session:
                self.session = session
                await cmd(self, *args, **kwargs)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(_do_command(cmd, *args, **kwargs))


cmd_dir = Path(__file__).parent / "commands"


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    "-c",
    "--config",
    default=Path(Path.home(), ".config", "spritzle"),
    show_default=True,
)
@click.option("-h", "--host", default="127.0.0.1", show_default=True)
@click.option("-p", "--port", default=8080, type=int, show_default=True)
@click.option("-t", "--token", default="")
@click.pass_context
def cli(ctx, config, host, port, token):
    """Command-line interface for Spritzle."""
    ctx.obj = Client(host, port, config, token)


def load_commands():
    """Adds all commands found in 'commands' subdirectory."""
    for module_info in pkgutil.iter_modules([cmd_dir]):
        try:
            mod = importlib.import_module("spritzle.cli.commands." + module_info.name)
        except ImportError as e:
            click.echo(e, file=sys.stderr)
        else:
            cli.add_command(mod.command, name=module_info.name)


load_commands()


if __name__ == "__main__":
    cli()
