Spritzle
========

Spritzle is a lightweight bittorrent client built around libtorrent. It aims
to provide a simple REST interface to libtorrent. Any additional
functionality should be provided by a hook extending spritzle.

Installation
------------

Use [uv](https://github.com/astral-sh/uv) to manage dependencies and install the package.

```bash
git clone https://github.com/AndrewResch/spritzle.git
cd spritzle
uv sync
```

Development
-----------

To run the daemon locally during development:

```bash
uv run spritzled
```

To run the CLI:

```bash
uv run spritzle
```

Testing
-------

To run the tests:

```bash
uv run pytest
```

Documentation
-------------

* [spritzled Daemon Guide](docs/spritzled.md): Daemon CLI options, configuration keys, systemd service setup, and token generation.
* [spritzle CLI Guide](docs/spritzle.md): Command-line client usage, subcommands reference, authentication, and bash completion.
* [REST API Interface](docs/interface.md): Full HTTP REST API reference and examples.
* [Hooks System](docs/hooks.md): Custom scripting with libtorrent status alerts.
* [Architecture Design](docs/design.md): System architecture and request lifecycle.

Authors
-------

* Andrew Resch <andrewresch@gmail.com>

