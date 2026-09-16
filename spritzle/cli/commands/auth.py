import json
import os
from pathlib import Path
import sys

import click


from spritzle.cli.display import print_error, print_success


@click.command("auth", short_help="Generate an authentication token.")
@click.option("--password", required=True, prompt=True, hide_input=True)
@click.pass_obj
def command(client, password):
    client.do_command(f, password)


async def f(client, password):
    data = {"password": password}
    async with client.session.post(client.url("auth"), json=data) as resp:
        if resp.status != 200:
            err_msg = resp.reason
            try:
                err_json = await resp.json()
                err_msg = err_json.get("message") or err_json.get("reason") or err_msg
            except Exception:
                pass
            print_error(
                f"Authentication failed: {err_msg} (HTTP {resp.status})",
                color_opt=getattr(client, "color", None),
            )
            sys.exit(1)

        d = await resp.json()
        tf = Path(client.config, "tokens")

        t = {}
        if tf.exists():
            try:
                with tf.open(mode="r") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        t = loaded
            except Exception:
                t = {}

        tf.parent.mkdir(parents=True, exist_ok=True)
        with tf.open(mode="w") as f:
            t[f"{client.host}:{client.port}"] = d["token"]
            json.dump(t, f, indent=2)
        try:
            os.chmod(tf, 0o600)
        except OSError:
            pass

        print_success(
            f"Token for {client.host}:{client.port} updated.",
            color_opt=getattr(client, "color", None),
        )

