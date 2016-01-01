# Copyright (c) 2014, Marcel Hellkamp.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import bottle
import os
import asyncio

class AiohttpServer(bottle.ServerAdapter):
    """ Untested.
        aiohttp
        https://pypi.python.org/pypi/aiohttp/

        TODO: Remove this class once it is available in a
        released bottle.py version
    """

    def __init__(self, host='127.0.0.1', port=8080, **options):
        self.loop = asyncio.get_event_loop()
        super(AiohttpServer, self).__init__(host, port, **options)

    def run(self, handler):
        from aiohttp.wsgi import WSGIServerHttpProtocol

        protocol_factory = lambda: WSGIServerHttpProtocol(
            handler,
            readpayload=True,
            debug=bottle.DEBUG)
        self.loop.run_until_complete(self.loop.create_server(protocol_factory,
                                                             self.host,
                                                             self.port))


        if 'BOTTLE_CHILD' in os.environ:
            import signal
            signal.signal(signal.SIGINT, self.stop)

        self.loop.run_forever()

    def stop(self):
        self.loop.stop()