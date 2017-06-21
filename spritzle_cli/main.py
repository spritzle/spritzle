# -*- coding: utf-8 -*-
import click
import os
import sys


CONTEXT_SETTINGS = dict(auto_envvar_prefix='SPRITZLE')


class Context(object):
    pass


pass_context = click.make_pass_decorator(Context, ensure=True)
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
@click.option('-h', '--host', default='127.0.0.1', show_default=True)
@click.option('-p', '--port', default=8080, type=int, show_default=True)
@pass_context
def main(ctx, host, port):
    """Command-line interface for Spritzle."""
    ctx.host = host
    ctx.port = port


if __name__ == "__main__":
    main()
