#!/usr/bin/env python

import asyncio
import csv
import datetime as dt
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

provision_log_path = Path(config['provisioning']['path'])

GW_SEND = b"GWS"
GW_CONTROL = b"GWC"

async def index(_):
    raise web.HTTPFound(location='index.html')

async def wave(request: web.Request):
    body = await request.json()
    rows = body["row"].strip()
    start = int(body["start"])
    stop = int(body["stop"])
    delay = int(body["delay"])

    for i in range(start, stop+1):
        for row in rows:
            id = RowColToId(row, i)
            msg = GW_SEND + pack_message("A", id)
            logger.debug("serial write: %s", msg)
            request.app['serial_writer'].write(msg)
        await asyncio.sleep(delay / 1000)
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
    prov_queue = request.app['serial_response_queue_prov']
    clear_queue(prov_queue)
    body = await request.json()
    msg = GW_SEND + pack_message("*", 0, "P")
    logger.debug("serial write: %s", msg)
    request.app['serial_writer'].write(msg)

    try:
        received = await asyncio.wait_for(prov_queue.get(), 10)
        received = received.decode()
        mb_serial = int(received[4:])
    except asyncio.TimeoutError:
        return web.json_response({})

    row, col = body['row'], int(body['col'])
    logger.debug(f"provision: {mb_serial} to {row}{col}")
    with provision_log_path.open("a") as prov_log:
        prov_log.write(f"{dt.datetime.now()},{mb_serial},{row}{col}\n")

    msg = GW_SEND + pack_message("*", mb_serial, "I", RowColToId(row, col))
    request.app['serial_writer'].write(msg)

    print(f"SAM1: {pack_message("*", mb_serial, "I")}")
    print(f"SAM2: {pack_message("*", mb_serial, "I", RowColToId(row, col))}")

    logger.debug("serial write: %s", msg)
    logger.debug(f"serial write: {mb_serial} {RowColToId(row, col)}")

    result = f"{mb_serial} -> {row}{col}"
    return web.json_response({'result': result})

async def provision_ids_send(request):
    body = await request.json()
    prov_only = body["prov_only"]
    id_lookup = load_provisioning()
    logger.debug(f"provision_ids_send: {len(id_lookup)=}")
    for mb_serial, pos in id_lookup.items():
        if prov_only and not prov_only in pos:
            continue
        row, col = pos[0], int(pos[1:])
        pos_id = RowColToId(row, col)
        logger.debug(f"provision_ids_send: {mb_serial=} {row=} {col=} {pos_id=}")
        msg = GW_SEND + pack_message("*", mb_serial, "I", pos_id)
        request.app['serial_writer'].write(msg)
        await asyncio.sleep(0.5)

    return web.json_response({})

async def serial_receiver(r, queues: dict[str,asyncio.Queue]):
    while True:
        msg = await r.readuntil(b'\n')
        msg = msg.rstrip()
        logger.debug(f'received: {msg.decode()}')
        if msg.startswith(b"GWC") and len(msg) > 3:
            m1, _, m2 = msg.partition(b",")
            if m1 != m2:
                logger.warning(f"Corrupt serial message: {m1} != {m2}")
                continue
            key = chr(m1[3])
            logger.debug(f"put in queue {key}")
            await queues[key].put(m1.rstrip())


async def run_serial_comms(app: web.Application):
    reader, writer = await serial_asyncio.open_serial_connection(
        url=serial_config['dev'], baudrate=serial_config['baudrate'])
    logger.debug(f"Opened serial connections: reader : {reader}")
    logger.debug(f"Opened serial connections: writer : {writer}")
    app['serial_reader'] = reader
    app['serial_writer'] = writer
    app['serial_response_queue_status'] = asyncio.Queue()
    app['serial_response_queue_prov'] = asyncio.Queue()
    receiver = asyncio.create_task(serial_receiver(reader, {
        "H": app['serial_response_queue_status'],
        "Q": app['serial_response_queue_prov'],
        }))
    yield
    logger.debug("Done")

def pack_message(key: str, to_id: int, value: str | None = None, extra_val: None | int = None) -> bytes:
    buf = struct.pack("<cl", key[0].encode(encoding='utf-8'), to_id)
    if isinstance(value, str):
        buf += value.encode(encoding='utf-8')
    if isinstance(value, int):
        buf += struct.pack("<l", value)

    if isinstance(extra_val, int):
        buf += struct.pack("<l", extra_val)

    logger.debug(f'pack_message: {len(buf)=}: {key=} {to_id=} {value=} {extra_val=}')

    return (buf.hex() + "\n").encode(encoding='utf-8')

def RowColToId(row: int| str, col: int) -> int:
    print(f"RowColToId {row=} {col=}")
    if isinstance(row, str):
        row = ord(row[0].lower()) - ord("a") + 1

    print(f"RowColToId {row=} {col=}")
    return (256 * row) + col

def clear_queue(queue: asyncio.Queue):
    while True:
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            return

def load_provisioning() -> dict[int, str]:
    id_lookup = {}
    with provision_log_path.open() as prov_file:
        for row in csv.reader(prov_file):
            if len(row) == 0 or row[0][0] == "#":
                continue
            _, mb_id, pos = row
            id_lookup[int(mb_id)] = pos
    return id_lookup

def main():
    app = web.Application()
    app.cleanup_ctx.append(run_serial_comms)

    app.add_routes([web.post('/wave', wave)])
    app.add_routes([web.post('/config', set_config)])
    app.add_routes([web.post('/prov', provision_ids)])
    app.add_routes([web.post('/prov_send', provision_ids_send)])
    app.add_routes([web.get('/check', check_status)])
    app.add_routes([web.get('/', index)])
    app.add_routes([web.static('/', Path('static'))])

    web.run_app(app, host = server_config.get('host', '0.0.0.0'),
                port = server_config.get('port', 8080))

def check_provisioning():
    by_serial = {}
    by_pos = {}
    with provision_log_path.open() as prov_file:
        for row in csv.reader(prov_file):
            if len(row) == 0 or row[0][0] == "#":
                continue
            _, serial, pos = row
            pair = (serial, pos)

            if serial in by_serial:
                old_pair = by_serial[serial]
                if pair == old_pair:
                    print(f"Dupe for {serial}: {old_pair} ~~ {pair}")
                else:
                    print(f"Conflict for {serial}: {old_pair} ~~ {pair}")

            if pos in by_pos:
                old_pair = by_pos[pos]
                if pair == old_pair:
                    print(f"Dupe for {pos}: {old_pair} ~~ {pair}")
                else:
                    print(f"Conflict for {pos}: {old_pair} ~~ {pair}")

            if not (-2**31 < int(serial) < 2**31):
                print(f"Serial not in int32 range: {serial}")

            by_serial[serial] = (serial, pos)
            by_pos[pos] = (serial, pos)

    rows = {pos[0] for pos in by_pos}
    rows = sorted(list(rows))
    cols = {int(pos[1:]) for pos in by_pos}
    cols = sorted(list(cols))
    print(f"{rows}")
    print(f"{cols}")
    for row in reversed(rows):
        print(f"{row}: ", end="")
        for col in cols:
            pos = f"{row}{col}"
            if pos in by_pos:
                print(f"{col} ", end="")
            else:
                print(f"{"_"*len(str(col))} ", end="")
        print()



if __name__ == "__main__":
    check_provisioning()
    main()
