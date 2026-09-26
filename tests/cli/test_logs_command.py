import json
import logging
from pathlib import Path

from click.testing import CliRunner

from spritzle.cli.main import cli as spritzle_cli
from spritzle.daemon.keys import APP_KEY_CORE
from tests.daemon.common import torrent_dir


def test_logs_command_basic(cli):
    log = logging.getLogger("spritzle")
    log.info("CLI test info log line")
    log.warning("CLI test warning log line")

    runner = CliRunner()
    result = runner.invoke(spritzle_cli, ["logs"])
    assert result.exit_code == 0
    assert "CLI test info log line" in result.output or "CLI test warning log line" in result.output


def test_logs_command_plain(cli):
    log = logging.getLogger("spritzle")
    log.setLevel(logging.DEBUG)
    log.info("Plain mode log test message")

    runner = CliRunner()
    result = runner.invoke(spritzle_cli, ["logs", "--plain"])
    assert result.exit_code == 0
    assert "Plain mode log test message" in result.output


def test_logs_command_json(cli):
    log = logging.getLogger("spritzle")
    log.warning("JSON mode log test message")

    runner = CliRunner()
    result = runner.invoke(spritzle_cli, ["logs", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert any(x.get("message") == "JSON mode log test message" for x in data)


def test_logs_command_filters(cli):
    log = logging.getLogger("spritzle")
    log.debug("Debug only item")
    log.error("Fatal error item")

    runner = CliRunner()
    result = runner.invoke(spritzle_cli, ["logs", "--level", "error", "--plain"])
    assert result.exit_code == 0
    assert "Fatal error item" in result.output
    assert "Debug only item" not in result.output


def test_logs_command_clear(cli):
    log = logging.getLogger("spritzle")
    log.info("Item before clear")

    runner = CliRunner()
    clear_res = runner.invoke(spritzle_cli, ["logs", "--clear"])
    assert clear_res.exit_code == 0
    assert "cleared" in clear_res.output.lower()

    list_res = runner.invoke(spritzle_cli, ["logs", "--json", "--level", "info"])
    assert list_res.exit_code == 0
    data = json.loads(list_res.output)
    assert len(data) == 0


def test_log_command_not_registered(cli):
    runner = CliRunner()
    result = runner.invoke(spritzle_cli, ["log", "--help"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_add_command_with_flag(cli):
    torrent_file = Path(torrent_dir, "random_one_file.torrent")
    runner = CliRunner()
    result = runner.invoke(spritzle_cli, ["add", str(torrent_file), "--flag", "paused", "--plain"])
    assert result.exit_code == 0

    core = cli.app[APP_KEY_CORE]
    torrents = core.session.get_torrents()
    assert len(torrents) == 1
    assert torrents[0].status().paused is True
