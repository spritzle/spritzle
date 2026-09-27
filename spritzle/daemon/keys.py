import logging
from typing import Any, TYPE_CHECKING
import aiohttp.web

if TYPE_CHECKING:
    pass

APP_KEY_LOG = aiohttp.web.AppKey("spritzle.log", logging.Logger)
APP_KEY_CORE = aiohttp.web.AppKey("spritzle.core", Any)
APP_KEY_CONFIG = aiohttp.web.AppKey("spritzle.config", Any)
APP_KEY_IDENTITY = aiohttp.web.AppKey("spritzle.identity", Any)
APP_KEY_KEY_MANAGER = aiohttp.web.AppKey("spritzle.key_manager", Any)
REQ_KEY_AUTH_IDENTITY = getattr(aiohttp.web, "RequestKey", lambda name, t=Any: name)("auth_identity", Any)

