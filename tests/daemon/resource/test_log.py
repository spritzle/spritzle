import logging

from spritzle.daemon.logger import LogBufferHandler, get_log_buffer_handler


def test_log_buffer_handler_basics():
    handler = LogBufferHandler(max_size=5)
    logger = logging.getLogger("test_logger_buffer")
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    handler.clear()
    assert len(handler.get_logs()) == 0

    logger.debug("debug message")
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")

    logs = handler.get_logs()
    assert len(logs) == 4
    assert logs[0]["level"] == "DEBUG"
    assert logs[0]["message"] == "debug message"
    assert logs[1]["level"] == "INFO"
    assert logs[2]["level"] == "WARNING"
    assert logs[3]["level"] == "ERROR"

    # Filter by level
    warn_logs = handler.get_logs(level="WARNING")
    assert len(warn_logs) == 2
    assert [x["level"] for x in warn_logs] == ["WARNING", "ERROR"]

    # Filter by regex
    match_logs = handler.get_logs(regex=r"error.*")
    assert len(match_logs) == 1
    assert match_logs[0]["message"] == "error message"

    # Limit
    limited = handler.get_logs(limit=2)
    assert len(limited) == 2
    assert limited[-1]["message"] == "error message"

    # Test eviction when exceeding max_size (5)
    logger.critical("critical 1")
    logger.info("info 2")  # 6th message, evicts first
    assert len(handler.get_logs()) == 5
    assert handler.get_logs()[0]["message"] == "info message"

    # Test resize
    handler.set_max_size(2)
    assert len(handler.get_logs()) == 2
    assert handler.max_size == 2

    handler.clear()
    assert len(handler.get_logs()) == 0


async def test_get_log_endpoint(cli):
    log = logging.getLogger("spritzle")
    log.setLevel(logging.DEBUG)
    handler = get_log_buffer_handler()
    handler.clear()

    log.info("Server started test message")
    log.warning("Disk space warning test message")
    log.error("Network timeout error message")

    # 1. Fetch all logs
    resp = await cli.get("/log")
    assert resp.status == 200
    data = await resp.json()
    assert len(data) >= 3

    # 2. Filter by level
    resp = await cli.get("/log?level=WARNING")
    assert resp.status == 200
    warn_data = await resp.json()
    assert all(x["level"] in ("WARNING", "ERROR", "CRITICAL") for x in warn_data)

    # 3. Filter by regex
    resp = await cli.get("/log?regex=timeout")
    assert resp.status == 200
    regex_data = await resp.json()
    assert len(regex_data) >= 1
    assert any("timeout" in x["message"] for x in regex_data)

    # 4. Filter by limit
    resp = await cli.get("/log?limit=2")
    assert resp.status == 200
    lim_data = await resp.json()
    assert len(lim_data) <= 2

    # 5. Invalid parameters
    resp = await cli.get("/log?level=INVALID_LVL")
    assert resp.status == 400

    resp = await cli.get("/log?regex=[invalid(")
    assert resp.status == 400

    resp = await cli.get("/log?limit=-5")
    assert resp.status == 400

    resp = await cli.get("/log?since=notanumber")
    assert resp.status == 400


async def test_delete_log_endpoint(cli):
    log = logging.getLogger("spritzle")
    log.warning("Test entry to delete")

    resp = await cli.get("/log?level=WARNING")
    assert resp.status == 200
    assert len(await resp.json()) > 0

    resp = await cli.delete("/log")
    assert resp.status == 200
    assert (await resp.json())["status"] == "cleared"

    resp = await cli.get("/log?level=WARNING")
    assert resp.status == 200
    assert len(await resp.json()) == 0


async def test_config_logging_dynamic_update(core):
    log_obj = logging.getLogger("spritzle")
    handler = get_log_buffer_handler()

    # Initial state
    core.config["log_level"] = "WARNING"
    core.config["log_buffer_size"] = 50

    assert log_obj.level == logging.WARNING
    assert handler.max_size == 50

    core.config["log_level"] = "DEBUG"
    core.config["log_buffer_size"] = 250

    assert log_obj.level == logging.DEBUG
    assert handler.max_size == 250


async def test_dynamic_log_file(core, tmp_path):
    log_obj = logging.getLogger("spritzle")
    log_file1 = tmp_path / "test1.log"
    log_file2 = tmp_path / "sub" / "test2.log"

    core.config["log_file"] = str(log_file1)
    log_obj.info("First log entry to file 1")
    for h in log_obj.handlers:
        h.flush()
    assert log_file1.exists()
    assert "First log entry to file 1" in log_file1.read_text()

    # Switch log file
    core.config["log_file"] = str(log_file2)
    log_obj.info("Second log entry to file 2")
    for h in log_obj.handlers:
        h.flush()
    assert log_file2.exists()
    assert "Second log entry to file 2" in log_file2.read_text()
    assert "Second log entry to file 2" not in log_file1.read_text()

    # Remove log file via empty string
    core.config["log_file"] = ""
    file_handlers = [h for h in log_obj.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 0

    # Test re-adding and then deleting via del
    core.config["log_file"] = str(log_file1)
    file_handlers = [h for h in log_obj.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1
    del core.config["log_file"]
    file_handlers = [h for h in log_obj.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 0


async def test_startup_logfile_takes_precedence(tmp_path):
    from spritzle.daemon.config import Config
    from spritzle.daemon.core import Core

    cfg_dir = tmp_path / "cfg"
    st_dir = tmp_path / "st"
    cfg_dir.mkdir()
    st_dir.mkdir()

    cfg = Config(config_dir=str(cfg_dir))
    startup_log = tmp_path / "startup.log"
    core = Core(cfg, state_dir=st_dir, startup_logfile=str(startup_log))

    try:
        log_obj = logging.getLogger("spritzle")
        log_obj.info("startup message")
        for h in log_obj.handlers:
            h.flush()
        assert startup_log.exists()
        assert "startup message" in startup_log.read_text()

        # Config change should not override startup_logfile
        cfg_log = tmp_path / "config.log"
        core.config["log_file"] = str(cfg_log)
        log_obj.info("after config change")
        for h in log_obj.handlers:
            h.flush()

        assert not cfg_log.exists()
        assert "after config change" in startup_log.read_text()
    finally:
        await core.stop(save=False)
        core.startup_logfile = None
        core._update_file_handler(None)


def test_create_file_handler(tmp_path):
    from spritzle.daemon.logger import create_file_handler
    from logging.handlers import RotatingFileHandler

    rfh = create_file_handler(tmp_path / "sub1" / "rot.log", max_bytes=1024, backup_count=3)
    assert isinstance(rfh, RotatingFileHandler)
    rfh.close()

    fh = create_file_handler(tmp_path / "sub2" / "plain.log", max_bytes=0)
    assert isinstance(fh, logging.FileHandler)
    assert not isinstance(fh, RotatingFileHandler)
    fh.close()
