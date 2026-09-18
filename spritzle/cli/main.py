import asyncio
import importlib
import json
from pathlib import Path


import pkgutil
import sys
from typing import Optional, Union

from urllib.parse import urlparse

import aiohttp
import click

from spritzle.cli.config import CLIConfig, RemotesConfig

CONTEXT_SETTINGS = dict(auto_envvar_prefix="SPRITZLE")


class Client(object):
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        config: Union[Path, str, None] = None,
        token: Optional[str] = None,
        color: Optional[bool] = None,
        remote: Optional[str] = None,
    ):

        if config is None:
            self.config = Path(Path.home(), ".config", "spritzle")
        else:
            self.config = Path(config)

        self.cli_config = CLIConfig(config_dir=self.config)
        self.remotes = RemotesConfig(config_dir=self.config)
        self.remotes_config = self.remotes

        has_custom_host_or_port = (
            host is not None
            or port is not None
            or self.cli_config.is_modified("host")
            or self.cli_config.is_modified("port")
        )

        if not has_custom_host_or_port:
            self.remotes.ensure_local_remote()

        self.color = color if color is not None else self.cli_config.get("color", None)
        self.plain = bool(self.cli_config.get("plain", False))

        self.remote_name = remote or self.remotes.get_default_remote()
        remote_data = self.remotes.get_remote(self.remote_name) if self.remote_name else None

        if remote_data and not (remote is None and has_custom_host_or_port):
            self.base_url = remote_data.get("url", "").rstrip("/")
            self.expected_daemon_id = remote_data.get("daemon_id")
            self.token = token if token is not None else remote_data.get("key", "")
            parsed = urlparse(self.base_url)
            self.host = parsed.hostname or "127.0.0.1"
            self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        else:
            self.base_url = None
            self.expected_daemon_id = None
            self.host = host if host is not None else str(self.cli_config.get("host", "127.0.0.1"))
            self.port = int(port if port is not None else self.cli_config.get("port", 8080))
            self.token = token if token else str(self.cli_config.get("token", ""))

            if not self.token and Path(self.config, "tokens").exists():
                try:
                    with Path(self.config, "tokens").open("r", encoding="utf-8") as f:
                        d = json.load(f)
                        if isinstance(d, dict) and f"{self.host}:{self.port}" in d:
                            self.token = d[f"{self.host}:{self.port}"]
                except Exception:
                    pass


        self.session = None

    def url(self, path: str, query: str = "") -> str:
        path = path.lstrip("/")
        if self.base_url:
            base = self.base_url
        else:
            host = self.host
            if ":" in host and not (host.startswith("[") and host.endswith("]")):
                host = f"[{host}]"
            base = f"http://{host}:{self.port}"
        if query:
            return f"{base}/{path}?{query}"
        return f"{base}/{path}"

    def do_command(self, cmd, *args, **kwargs):
        async def _do_command(cmd, *args, **kwargs):
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            trace_config = aiohttp.TraceConfig()

            async def on_request_end(session, trace_config_ctx, params):
                daemon_id = params.response.headers.get("X-Spritzle-Daemon-Id")
                if daemon_id and self.expected_daemon_id and daemon_id != self.expected_daemon_id:
                    from spritzle.cli.display import print_error

                    print_error(
                        f"Daemon identity mismatch for remote '{self.remote_name}'!\n"
                        f"Expected: {self.expected_daemon_id}\n"
                        f"Found:    {daemon_id}\n"
                        "Refusing to communicate with unexpected daemon.",
                        color_opt=self.color,
                    )
                    sys.exit(1)

            trace_config.on_request_end.append(on_request_end)

            async with aiohttp.ClientSession(headers=headers, trace_configs=[trace_config]) as session:
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
@click.option("-r", "--remote", default=None, help="Remote daemon profile to use.")
@click.option("-h", "--host", default=None, help="Daemon host. [default: 127.0.0.1]")
@click.option("-p", "--port", default=None, type=int, help="Daemon port. [default: 8080]")
@click.option("-t", "--token", default=None, help="Authentication API key / token.")
@click.option("--color/--no-color", default=None, help="Enable or disable color output.")
@click.pass_context
def cli(ctx, config, remote, host, port, token, color):
    """Command-line interface for Spritzle."""
    ctx.obj = Client(host=host, port=port, config=config, token=token, color=color, remote=remote)




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
