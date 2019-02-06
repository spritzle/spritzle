from pathlib import Path
import sys

import click
import yaml


@click.command('auth', short_help='Generate an authentication token.')
@click.option('--password', required=True, prompt=True, hide_input=True)
@click.pass_obj
def command(client, password):
    client.do_command(f, password)


async def f(client, password):
    data = {
        'password': password,
    }
    async with client.session.post(client.url('auth'), json=data) as resp:
        if resp.status != 200:
            click.echo(f'Error: {resp}', file=sys.stderr)
            sys.exit(1)

        d = await resp.json()
        tf = Path(client.config, 'tokens')

        if tf.exists():
            t = yaml.safe_load(tf.open(mode='r')) or {}
        else:
            t = {}

        with tf.open(mode='w') as f:
            t[f'{client.host}:{client.port}'] = d['token']
            yaml.safe_dump(t, f, default_flow_style=False)

        click.echo(f'Token for {client.host}:{client.port} updated.')
