#!/usr/bin/env python

import asyncio

from aiohttp import web
import serial_asyncio

from config import get_config

config = get_config()
server_config = config['server']
serial_config = config['serial']



async def hello(request):
    print(f"{request=}")
    return web.Response(text="Hello, world")

async def send(request):
    print(f"{request=}")
    for i in range(1, 5):
        request.app['serial_writer'].write(f"A,{i}\n".encode(encoding='utf8'))
        await asyncio.sleep(0.5)
    return web.Response(text="send")

async def run_serial_comms(app: web.Application):
    reader, writer = await serial_asyncio.open_serial_connection(url=serial_config['dev'],
                                                                 baudrate=serial_config['baudrate'])
    print(f"Opened serial connections:\n {reader}\n {writer}")
    app['serial_reader'] = reader
    app['serial_writer'] = writer
    yield
    print("Done")

def main():
    app = web.Application()
    app.cleanup_ctx.append(run_serial_comms)

    app.add_routes([web.get('/', hello)])
    app.add_routes([web.get('/send', send)])

    web.run_app(app, host = server_config.get('host', '0.0.0.0'),
                port = server_config.get('port', 8080))

if __name__ == "__main__":
    main()
