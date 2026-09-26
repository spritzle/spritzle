from collections import deque
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
import threading
from typing import Any, Dict, List, Optional, Union


class LogBufferHandler(logging.Handler):
    """An in-memory ring buffer logging handler."""

    def __init__(self, max_size: int = 1000):
        super().__init__()
        self.max_size = max(1, int(max_size))
        self.buffer: deque = deque(maxlen=self.max_size)
        self._lock = threading.Lock()

    def set_max_size(self, new_size: int) -> None:
        """Resize the in-memory log buffer."""
        with self._lock:
            self.max_size = max(1, int(new_size))
            new_buffer = deque(self.buffer, maxlen=self.max_size)
            self.buffer = new_buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            entry: Dict[str, Any] = {
                "timestamp": record.created,
                "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": msg,
                "module": record.module,
                "lineno": record.lineno,
            }
            with self._lock:
                self.buffer.append(entry)
        except Exception:
            self.handleError(record)

    def get_logs(
        self,
        level: Optional[str] = None,
        regex: Optional[str] = None,
        since: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve and filter log entries from the ring buffer."""
        level_val = 0
        if level:
            level_str = level.strip().upper()
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "WARN": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }
            if level_str not in level_map:
                raise ValueError(f"Invalid log level '{level}'")
            level_val = level_map[level_str]

        compiled_regex = None
        if regex:
            try:
                compiled_regex = re.compile(regex)
            except re.error as ex:
                raise ValueError(f"Invalid regular expression '{regex}': {ex}")

        with self._lock:
            entries = list(self.buffer)

        results: List[Dict[str, Any]] = []
        for entry in entries:
            if since is not None and entry["timestamp"] < since:
                continue
            if level_val:
                entry_level_val = getattr(logging, entry["level"], 0)
                if entry_level_val < level_val:
                    continue
            if compiled_regex and not compiled_regex.search(entry["message"]):
                continue
            results.append(entry)

        if limit is not None and limit > 0:
            results = results[-limit:]

        return results

    def clear(self) -> None:
        with self._lock:
            self.buffer.clear()


_global_log_buffer_handler: Optional[LogBufferHandler] = None


def get_log_buffer_handler(max_size: int = 1000) -> LogBufferHandler:
    global _global_log_buffer_handler
    if _global_log_buffer_handler is None:
        _global_log_buffer_handler = LogBufferHandler(max_size=max_size)
    return _global_log_buffer_handler


def create_file_handler(
    logfile: Union[str, Path],
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    formatter: Optional[logging.Formatter] = None,
) -> logging.Handler:
    path = Path(os.path.expanduser(str(logfile))).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if formatter is None:
        formatter = logging.Formatter(
            "[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s"
        )
    if max_bytes > 0:
        from logging.handlers import RotatingFileHandler

        handler: logging.Handler = RotatingFileHandler(
            str(path), maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
    else:
        handler = logging.FileHandler(str(path), encoding="utf-8")
    handler.setLevel(logging.NOTSET)
    handler.setFormatter(formatter)
    return handler


def setup_logger(
    name=__name__,
    logfile=None,
    level: Union[int, str] = logging.DEBUG,
    buffer_size: int = 1000,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
):
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    if isinstance(level, str):
        level = level_map.get(level.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.propagate = False
    logger.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)

    formatter = logging.Formatter(
        "[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s"
    )
    stream_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)

    buffer_handler = get_log_buffer_handler(max_size=buffer_size)
    buffer_handler.setFormatter(formatter)
    buffer_handler.setLevel(logging.NOTSET)
    if buffer_handler not in logger.handlers:
        logger.addHandler(buffer_handler)

    filehandler = None
    if logfile:
        filehandler = create_file_handler(
            logfile, max_bytes=max_bytes, backup_count=backup_count, formatter=formatter
        )
        logger.addHandler(filehandler)

    if level == logging.DEBUG:
        for log in (
            "aiohttp.access",
            "aiohttp.client",
            "aiohttp.internal",
            "aiohttp.server",
            "aiohttp.web",
            "aiohttp.websocket",
        ):
            logging.getLogger(log).setLevel(level)
            logging.getLogger(log).addHandler(stream_handler)
            if buffer_handler not in logging.getLogger(log).handlers:
                logging.getLogger(log).addHandler(buffer_handler)
            if filehandler and filehandler not in logging.getLogger(log).handlers:
                logging.getLogger(log).addHandler(filehandler)

    return logger

