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

Interface
---------

A command-line client is included as the `spritzle` command.

Authors
-------

* Andrew Resch <andrewresch@gmail.com>
