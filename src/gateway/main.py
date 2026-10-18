#!/usr/bin/env python

import asyncio
import csv
import datetime as dt
import json
import logging
from pathlib import Path
import struct
import time

from aiohttp import web
import numpy
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

CORS_ALLOW = "http://localhost:3000"
CORS_HEADER = {"Access-Control-Allow-Origin": CORS_ALLOW}

async def index(_):
    raise web.HTTPFound(location='index.html')

async def wave(request: web.Request):
    body = await request.json()
    rows = body["row"].strip()
    start = int(body["start"])
    stop = int(body["stop"])
    delay = int(body["delay"])
    writer = request.app['gateway']['serial_writer']

    for i in range(start, stop+1):
        for row in rows:
            id = RowColToId(row, i)
            serial_write(writer, GW_SEND + pack_message("A", id))
        await asyncio.sleep(delay / 1000)
    return web.Response(text="done")

async def set_config(request: web.Request):
    body = await request.json()
    writer = request.app['gateway']['serial_writer']
    for config_name, key in (('volume', 'V'), ('pitch', 'T'), ('length', 'L'), ('count', 'C')):
        if config_name in body:
            value = int(body[config_name])
            serial_write(writer, GW_SEND + pack_message(key, 0, value))
    return web.Response(text="done")

async def check_status(request: web.Request):
    now = time.monotonic()
    stale = now - 30
    heartbeats = request.app['gateway']['heartbeats']

    status_result = {}
    if heartbeats['gateway'] > stale:
        status_result['gateway'] = "Good"
    else:
        status_result['gateway'] = f"Last heartbeat {int(now - heartbeats['gateway'])}s ago"

    pattern_shape = request.app['gateway']['pattern']['frames'].shape
    status_result["pattern_info"] = f"{pattern_shape[0]}x{pattern_shape[1]} {pattern_shape[2]} frames"

    return web.json_response(status_result)

async def provision_ids(request):
    prov_queue = request.app['serial_response_queue_prov']
    clear_queue(prov_queue)
    body = await request.json()
    writer = request.app['gateway']['serial_writer']
    serial_write(writer, GW_SEND + pack_message("*", 0, "P"))

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

    serial_write(writer, GW_SEND + pack_message("*", mb_serial, "I", RowColToId(row, col)))

    result = f"{mb_serial} -> {row}{col}"
    return web.json_response({'result': result})

async def provision_ids_send(request):
    body = await request.json()
    prov_only = body["prov_only"]
    id_lookup = load_provisioning()
    logger.debug(f"provision_ids_send: {len(id_lookup)=}")
    writer = request.app['gateway']['serial_writer']
    for mb_serial, pos in id_lookup.items():
        if prov_only and not prov_only in pos:
            continue
        row, col = pos[0], int(pos[1:])
        pos_id = RowColToId(row, col)
        logger.debug(f"provision_ids_send: {mb_serial=} {row=} {col=} {pos_id=}")
        serial_write(writer, GW_SEND + pack_message("*", mb_serial, "I", pos_id))
        await asyncio.sleep(0.1)

    return web.json_response({})

async def set_pattern(request):
    body = await request.json()
    pattern = json.loads(body['pattern'])
    rows = int(body['rows'])
    cols = int(body['cols'])
    pattern_arr = numpy.array(pattern).reshape(rows, cols, -1)
    pattern_arr = numpy.flip(pattern_arr, axis=0)

    logger.info(f"Received pattern {pattern_arr.shape=}")
    #print(pattern_arr[:,:,0]) # frame zero

    request.app['gateway']['pattern']['frames'] = pattern_arr

    for i in range(pattern_arr.shape[2]):
        await show_pattern_frame(pattern_arr[:,:,i], request.app['gateway']['serial_writer'])
        await asyncio.sleep(0.5)

    return web.json_response({}, headers=CORS_HEADER)

async def show_pattern_frame(frame: numpy.typing.NDArray, writer):
    if frame.ndim != 2:
        raise ValueError("frame should be 2D")

    for row in range(frame.shape[0]):
        for col in range(frame.shape[1]):
            if frame[row, col] == 1:
                id = RowColToId(row+1, col+1)
                serial_write(writer, GW_SEND + pack_message("A", id))

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

async def gateway_heartbeat(writer):
    while True:
        serial_write(writer, GW_CONTROL + b"H\n")
        await asyncio.sleep(15)

async def gateway_heartbeat_watch(status_queue, heartbeats):
    while True:
        received = await status_queue.get()
        received = received.decode()

        if received == "GWCH":
            heartbeats['gateway'] = time.monotonic()


async def run_serial_comms(app: web.Application):
    reader, writer = await serial_asyncio.open_serial_connection(
        url=serial_config['dev'], baudrate=serial_config['baudrate'])
    logger.debug(f"Opened serial connections: reader : {reader}")
    logger.debug(f"Opened serial connections: writer : {writer}")


    gateway_data = {}
    gateway_data['serial_reader'] = reader
    gateway_data['serial_writer'] = writer

    queue_status = asyncio.Queue()
    queue_prov = asyncio.Queue()

    gateway_data['serial_response_queue_status'] = queue_status
    gateway_data['serial_response_queue_prov'] = queue_prov
    sr_task = asyncio.create_task(serial_receiver(reader, {
        "H": queue_status,
        "Q": queue_prov,
        }))

    gateway_data['heartbeats'] = {'gateway': 0}
    hb_task = asyncio.create_task(gateway_heartbeat(writer))
    hbw_task = asyncio.create_task(gateway_heartbeat_watch(queue_status, gateway_data['heartbeats']))

    gateway_data['pattern'] = {"frames": numpy.array([[[0]]])}

    app['gateway'] = gateway_data
    yield
    logger.debug("Done")

def serial_write(writer, msg):
    logger.debug("serial write: %s", msg)
    writer.write(msg)

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
    app.add_routes([web.post('/set_pattern', set_pattern)])
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
