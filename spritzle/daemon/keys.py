import logging
from typing import Any, TYPE_CHECKING
import aiohttp.web

if TYPE_CHECKING:
    pass

APP_KEY_LOG = aiohttp.web.AppKey("spritzle.log", logging.Logger)
APP_KEY_CORE = aiohttp.web.AppKey("spritzle.core", Any)
APP_KEY_CONFIG = aiohttp.web.AppKey("spritzle.config", Any)
