import logging


def setup_logger(name=__name__, logfile=None, level=logging.DEBUG):
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

    if isinstance(level, str):
        level = level_map[level]

    logger = logging.getLogger(name)
    logger.propagate = False
    logger.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)

    formatter = logging.Formatter(
        '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s')
    stream_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)

    if logfile:
        filehandler = logging.FileHandler(logfile)
        filehandler.setLevel(logging.NOTSET)
        filehandler.setFormatter(formatter)
        logger.addHandler(filehandler)
    if level == logging.DEBUG:
        for log in (
                'aiohttp.access',
                'aiohttp.client',
                'aiohttp.internal',
                'aiohttp.server',
                'aiohttp.web',
                'aiohttp.websocket'):
            logging.getLogger(log).setLevel(level)
            logging.getLogger(log).addHandler(stream_handler)

    return logger
