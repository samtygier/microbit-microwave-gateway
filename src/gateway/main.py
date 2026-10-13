#!/usr/bin/env python

import asyncio
import logging
from pathlib import Path
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

GW_SEND = b"GWS"
GW_CONTROL = b"GWC"

async def index(_):
    raise web.HTTPFound(location='index.html')

async def wave(request: web.Request):
    body = await request.json()
    start = int(body["start"])
    stop = int(body["stop"])

    for i in range(start, stop+1):
        id = RowColToId(1, i)
        msg = GW_SEND + pack_message("A", id)
        logger.debug("serial write: %s", msg)
        request.app['serial_writer'].write(msg)
        await asyncio.sleep(0.5)
    return web.Response(text="done")

async def set_config(request: web.Request):
    body = await request.json()
    for config_name, key in (('volume', 'V'), ('pitch', 'T'), ('length', 'L'), ('count', 'C')):
        if config_name in body:
            value = int(body[config_name])
            msg = GW_SEND + pack_message(key, 0, value)
            logger.debug("serial write: %s", msg)
            request.app['serial_writer'].write(msg)
    return web.Response(text="done")

async def check_status(request: web.Request):
    rec_queue = request.app['serial_response_queue_status']
    clear_queue(rec_queue)
    msg = GW_CONTROL + b"H\n"
    logger.debug("serial write: %s", msg)
    request.app['serial_writer'].write(msg)

    try:
        received = await asyncio.wait_for(rec_queue.get(), 1)
        received = received.decode()
    except asyncio.TimeoutError:
        received = ""
    if received == "GWCH":
        gateway_status = "Good"
    else:
        gateway_status = "Bad"

    return web.json_response({"gateway": gateway_status})

async def provision_ids(request):
    msg = GW_SEND + pack_message("*", 0, "P")
    logger.debug("serial write: %s", msg)
    request.app['serial_writer'].write(msg)
    return web.Response(text="start provisioning mode")

async def serial_receiver(r, queue: asyncio.Queue):
    while True:
        msg = await r.readuntil(b'\n')
        await queue.put(msg.rstrip())
        logger.debug(f'received: {msg.rstrip().decode()}')


async def run_serial_comms(app: web.Application):
    reader, writer = await serial_asyncio.open_serial_connection(
        url=serial_config['dev'], baudrate=serial_config['baudrate'])
    logger.debug(f"Opened serial connections: reader : {reader}")
    logger.debug(f"Opened serial connections: writer : {writer}")
    app['serial_reader'] = reader
    app['serial_writer'] = writer
    app['serial_response_queue_status'] = asyncio.Queue()
    receiver = asyncio.create_task(serial_receiver(reader, app['serial_response_queue_status']))
    yield
    logger.debug("Done")

def pack_message(key: str, to_id: int, value: str | None = None) -> bytes:
    buf = struct.pack("<cL", key[0].encode(encoding='utf-8'), to_id)
    if isinstance(value, str):
        buf += value.encode(encoding='utf-8')
    if isinstance(value, int):
        buf += struct.pack("<L", value)

    return (buf.hex() + "\n").encode(encoding='utf-8')

def RowColToId(row: int, column: int) -> int:
    return (256 * row) + column

def clear_queue(queue: asyncio.Queue):
    while True:
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            return

def main():
    app = web.Application()
    app.cleanup_ctx.append(run_serial_comms)

    app.add_routes([web.post('/wave', wave)])
    app.add_routes([web.post('/config', set_config)])
    app.add_routes([web.get('/prov', provision_ids)])
    app.add_routes([web.get('/check', check_status)])
    app.add_routes([web.get('/', index)])
    app.add_routes([web.static('/', Path('static'))])

    web.run_app(app, host = server_config.get('host', '0.0.0.0'),
                port = server_config.get('port', 8080))

if __name__ == "__main__":
    main()
