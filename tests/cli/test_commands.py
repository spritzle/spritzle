from click.testing import CliRunner
from spritzle.cli.main import cli as spritzle_cli


def test_list_commands(cli):
    """
    Test the 'list' command.

    The 'cli' fixture here is the aiohttp test client from tests/conftest.py.
    It has a running server at cli.server.
    """
    runner = CliRunner()

    # Run the 'list' command pointing to our test server
    # We use --token "" to bypass token file checks if any, though the test server might not require it depending on config
    # The default token logic in Client checks for a file if token is empty, but providing empty string usually works if auth is disabled or mocked.
    # Looking at conftest.py, auth doesn't seem explicitly disabled in 'setup_app', need to check.
    # But let's try basic connection first.

    result = runner.invoke(
        spritzle_cli, ["--port", str(cli.server.port), "--token", "test-token", "list"]
    )

    # Ideally, we should add some torrents to the core before listing,
    # but the 'cli' fixture setup (via 'app' -> 'core') creates a fresh core.
    # So the list should be empty or contain what we add.

    assert result.exit_code == 0
    # Depending on output format (table), we should at least see headers or empty state
    # spritzle list defaults to printing a table.
    print(result.output)


def test_stats_command(cli):
    """
    Test the 'stats' command.
    """
    runner = CliRunner()
    result = runner.invoke(
        spritzle_cli, ["--port", str(cli.server.port), "--token", "test-token", "stats"]
    )
    assert result.exit_code == 0
    print(result.output)
