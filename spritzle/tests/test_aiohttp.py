from unittest.mock import patch
import asyncio
import os
import signal

from spritzle.aiohttp import AiohttpServer

def test_aiohttp_run():
    def handler(*args, **kwargs):
        pass

    with patch('asyncio.get_event_loop'):
        a = AiohttpServer()
        a.run(handler)
        asyncio.get_event_loop.assert_called_once()

def test_aiohttp_run_bottle_child():
    def handler(*args, **kwargs):
        pass

    os.environ['BOTTLE_CHILD'] = ''
    with patch('asyncio.get_event_loop'):
        with patch('signal.signal'):
            a = AiohttpServer()
            a.run(handler)
            signal.signal.assert_called_once()