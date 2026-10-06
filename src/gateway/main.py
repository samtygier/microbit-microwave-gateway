#!/usr/bin/env python

import asyncio
import logging
import struct

from aiohttp import web
import serial_asyncio

from config import get_config

config = get_config()
server_config = config['server']
serial_config = config['serial']
logging_config = config['logging']

logger = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
                    level=logging_config['level'].upper())

async def hello(request):
    return web.Response(text="Hello, world")

async def send(request):
    for i in range(1, 6):
        msg = pack_message("A", i)
        logger.debug("serial write: %s", msg)
        request.app['serial_writer'].write(msg)
        await asyncio.sleep(0.5)
    return web.Response(text="send")


async def provision_ids(request):
    msg = pack_message("*", 0, "P")
    logger.debug("serial write: %s", msg)
    request.app['serial_writer'].write(msg)
    return web.Response(text="start provisioning mode")


async def run_serial_comms(app: web.Application):
    reader, writer = await serial_asyncio.open_serial_connection(url=serial_config['dev'],
                                                                 baudrate=serial_config['baudrate'])
    logging.debug(f"Opened serial connections: reader : {reader}")
    logging.debug(f"Opened serial connections: writer : {writer}")
    app['serial_reader'] = reader
    app['serial_writer'] = writer
    yield
    logging.debug("Done")

def pack_message(key: str, to_id: int, value: str | None = None) -> bytes:
    buf = struct.pack("<cL", key[0].encode(encoding='utf-8'), to_id)
    if isinstance(value, str):
        buf += value.encode(encoding='utf-8')

    return (buf.hex() + "\n").encode(encoding='utf-8')

def main():
    app = web.Application()
    app.cleanup_ctx.append(run_serial_comms)

    app.add_routes([web.get('/', hello)])
    app.add_routes([web.get('/send', send)])
    app.add_routes([web.get('/prov', provision_ids)])

    web.run_app(app, host = server_config.get('host', '0.0.0.0'),
                port = server_config.get('port', 8080))

if __name__ == "__main__":
    main()
