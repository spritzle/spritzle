from urllib.parse import urlparse
import json
import sys

import click


@click.command('add', short_help='Add a torrent to the session.')
@click.argument('path', required=True)
@click.option('--option', '-o', type=str, multiple=True,
              help=('A key=value pair to be passed to the add torrent '
                    'parameters. Can be specified multiple times.'))
@click.option('--tag', '-t', type=str, multiple=True,
              help=('Tag to apply to the torrent. Can be specified multiple '
                    'times.'))
@click.pass_obj
def command(client, path, option, tag):
    client.do_command(f, path, option, tag)


async def f(client, path, option, tag):
    args = dict([o.split('=') for o in option])
    data = {
        'args': json.dumps(args),
        'tags': json.dumps(tag),
    }

    if not urlparse(path).scheme:
        data['file'] = open(path, 'rb')
    else:
        data['url'] = path

    async with client.session.post(client.url('torrent'), data=data) as resp:
        if resp.status != 201:
            click.echo(
                f'Error adding torrent: {resp.status} {resp.reason}',
                file=sys.stderr
            )
            sys.exit(1)
        hash = resp.headers['Location'].split('/')[-1]
        click.echo(f'{hash} added successfully.')
