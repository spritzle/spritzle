import asyncio
import importlib
import os
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
        config: Union[Path, str, None] = None,
        color: Optional[bool] = None,
        remote: Optional[str] = None,
    ):

        if config is None:
            env_config = os.environ.get("SPRITZLE_CONFIG") or os.environ.get("SPRITZLE_CONFIG_DIR")
            if env_config:
                self.config = Path(env_config)
            else:
                self.config = Path(Path.home(), ".config", "spritzle")
        else:
            self.config = Path(config)

        self.cli_config = CLIConfig(config_dir=self.config)
        self.remotes = RemotesConfig(config_dir=self.config)
        self.remotes_config = self.remotes

        self.remotes.ensure_local_remote()

        self.color = color if color is not None else self.cli_config.get("color", None)
        self.plain = bool(self.cli_config.get("plain", False))
        self.theme = str(self.cli_config.get("theme", "modern") or "modern")

        self.remote_name = remote or self.remotes.get_default_remote()
        remote_data = self.remotes.get_remote(self.remote_name) if self.remote_name else None

        if remote_data:
            self.base_url = remote_data.get("url", "").rstrip("/")
            self.expected_daemon_id = remote_data.get("daemon_id")
            self.token = remote_data.get("key", "")
            self.insecure = bool(remote_data.get("insecure", False))
            self.ca_cert = remote_data.get("ca_cert")
            self.fingerprint = remote_data.get("fingerprint")
            parsed = urlparse(self.base_url)
            self.host = parsed.hostname or "127.0.0.1"
            self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        else:
            self.base_url = None
            self.expected_daemon_id = None
            self.token = ""
            self.insecure = False
            self.ca_cert = None
            self.fingerprint = None
            self.host = "127.0.0.1"
            self.port = 17382

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
            if not self.base_url and not self.token:
                from spritzle.cli.display import print_error

                print_error(
                    "No remote daemon configured.\n"
                    "Run 'spritzle remote add <name> <url>' or start 'spritzled' locally.",
                    color_opt=self.color,
                )
                sys.exit(1)

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

            import ssl
            connector = None
            if self.insecure:
                connector = aiohttp.TCPConnector(ssl=False)
            elif self.fingerprint:
                fp_bytes = bytes.fromhex(self.fingerprint.replace(":", "").strip())
                connector = aiohttp.TCPConnector(fingerprint=fp_bytes)
            elif self.ca_cert:
                ssl_ctx = ssl.create_default_context(cafile=self.ca_cert)
                connector = aiohttp.TCPConnector(ssl=ssl_ctx)

            async with aiohttp.ClientSession(
                headers=headers, trace_configs=[trace_config], connector=connector
            ) as session:
                self.session = session
                await cmd(self, *args, **kwargs)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_do_command(cmd, *args, **kwargs))
        except aiohttp.ClientConnectorCertificateError as e:
            from spritzle.cli.display import print_error

            print_error(
                f"TLS certificate verification failed for {self.url('')}: {e.certificate_error}\n"
                "If using a self-signed certificate, update the remote with --fingerprint, --ca-cert, or --insecure.",
                color_opt=self.color,
            )
            sys.exit(1)
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
@click.option("--color/--no-color", default=None, help="Enable or disable color output.")
@click.pass_context
def cli(ctx, config, remote, color):
    """Command-line interface for Spritzle."""
    ctx.obj = Client(config=config, color=color, remote=remote)




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
