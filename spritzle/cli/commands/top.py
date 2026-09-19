import click

from spritzle.cli.dashboard import run_dashboard


@click.command("top", short_help="Interactive live dashboard of active torrents.")
@click.option(
    "-i",
    "--interval",
    type=float,
    default=1.0,
    show_default=True,
    help="Refresh interval in seconds.",
)
@click.option(
    "-q",
    "--query",
    type=str,
    multiple=True,
    help="Query string used to filter the torrents (e.g. state=downloading).",
)
@click.option("--plain", is_flag=True, default=False, help="Force plain unstyled output.")
@click.pass_obj
def command(client, interval, query, plain):
    """Interactive, updating dashboard showing active torrents, transfer rates, ETA, and connected peers."""
    client.do_command(f, interval, query, plain)


async def f(client, interval: float, query, plain: bool = False):
    color_opt = getattr(client, "color", None)
    await run_dashboard(client, query=query, interval=interval, color_opt=color_opt, plain=plain)
