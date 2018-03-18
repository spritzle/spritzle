import asyncio
from pathlib import Path
import os
import sys

import aiohttp
import click
import yaml

CONTEXT_SETTINGS = dict(auto_envvar_prefix='SPRITZLE')


class Context(object):
    def __init__(self, host, port, config, token):
        self.host = host
        self.port = port
        self.config = Path(config)
        if not token and Path(self.config, 'tokens').exists():
            with Path(self.config, 'tokens').open() as f:
                d = yaml.safe_load(f)
                if f'{host}:{port}' in d:
                    self.token = d[f'{host}:{port}']
        else:
            self.token = token

        self.session = None

    def url(self, path):
        return f'http://{self.host}:{self.port}/{path}'

    def do_command(self, cmd, *args):
        async def _do_command(cmd, *args):
            headers = {
                'Authorization': self.token,
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                self.session = session
                await cmd(self, *args)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(_do_command(cmd, *args))


cmd_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'commands'))


class Main(click.MultiCommand):

    def list_commands(self, ctx):
        cmds = []
        for fn in os.listdir(cmd_dir):
            if not fn.startswith('_') and fn.endswith('.py'):
                cmds.append(fn[:-3])
        return sorted(cmds)

    def get_command(self, ctx, name):
        cmds = self.list_commands(ctx)
        if name not in cmds:
            cmds = ', '.join(cmds)
            click.echo(f'Valid commands: {cmds}')
            return
        try:
            mod = __import__('spritzle_cli.commands.' + name,
                             None, None, ['main'])
        except ImportError as e:
            click.echo(e, file=sys.stderr)
        return mod.main


@click.command(cls=Main, context_settings=CONTEXT_SETTINGS)
@click.option('-c', '--config', default=Path(Path.home(), '.config', 'spritzle'), show_default=True)
@click.option('-h', '--host', default='127.0.0.1', show_default=True)
@click.option('-p', '--port', default=8080, type=int, show_default=True)
@click.option('-t', '--token', default='')
@click.pass_context
def main(ctx, config, host, port, token):
    """Command-line interface for Spritzle."""
    ctx.obj = Context(host, port, config, token)


if __name__ == "__main__":
    main()
