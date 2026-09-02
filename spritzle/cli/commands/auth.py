import json
import os
from pathlib import Path
import sys

import click


@click.command("auth", short_help="Generate an authentication token.")
@click.option("--password", required=True, prompt=True, hide_input=True)
@click.pass_obj
def command(client, password):
    client.do_command(f, password)


async def f(client, password):
    data = {"password": password}
    async with client.session.post(client.url("auth"), json=data) as resp:
        if resp.status != 200:
            click.echo(f"Error: {resp}", file=sys.stderr)
            sys.exit(1)

        d = await resp.json()
        tf = Path(client.config, "tokens")

        t = {}
        if tf.exists():
            try:
                with tf.open(mode="r") as f:
                    t = json.load(f) or {}
            except Exception:
                t = {}

        with tf.open(mode="w") as f:
            t[f"{client.host}:{client.port}"] = d["token"]
            json.dump(t, f, indent=2)
        try:
            os.chmod(tf, 0o600)
        except OSError:
            pass

        click.echo(f"Token for {client.host}:{client.port} updated.")

