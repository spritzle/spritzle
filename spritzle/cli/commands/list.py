import sys

import click
from tabulate import tabulate


@click.command('list', short_help='List torrents in the session.')
@click.option('-f', '--fields', type=str, show_default=True,
              default=('name,state,progress,download_rate,upload_rate,'
                       'spritzle.tags'),
              help='Fields from the torrent status that will be printed.')
@click.option('--header/--no-header', default=True,
              help='Print header in output.')
@click.pass_obj
def command(client, fields, header):
    client.do_command(f, fields, header)


async def f(client, fields, header):
    type_formatters = {
        list: list_formatter,
    }

    fields = fields.split(',')
    async with client.session.get(client.url('torrent')) as resp:
        if resp.status != 200:
            click.echo(f'Error: {resp}', file=sys.stderr)
            sys.exit(1)
        torrents = await resp.json()

    table = []
    for torrent in torrents:
        async with client.session.get(client.url(f'torrent/{torrent}')) as resp:
            t = await resp.json()
            values = []
            for field in fields:
                value = t[field]
                values.append(
                    type_formatters.get(type(value), str)(value))
            table.append(values)

    tablefmt = 'simple'
    if not header:
        fields = []
        tablefmt = 'plain'

    print(tabulate(table, headers=fields, tablefmt=tablefmt))


def list_formatter(v):
    return ','.join(v)
