serial.onDataReceived(serial.delimiters(Delimiters.NewLine), function () {
    basic.showLeds(`
        # . . . .
        . . . . .
        . . . . .
        . . . . .
        . . . . .
        `)
    const message = serial.readUntil(serial.delimiters(Delimiters.NewLine))
    if(message.substr(0, 3) == "GWS"){
        const buf = Buffer.fromHex(message.substr(3))
        for (let i = 0; i < 5; i++) {
            radio.sendBuffer(buf)
            control.waitMicros(100)
        }
        serial.writeLine(`GW: radio sent len: ${buf.length}`)
    } else if (message.substr(0, 3) == "GWC"){
        handle_control(message.substr(3))
    }

    basic.clearScreen()
})

function handle_control(message: string){
    switch (message[0]){
        case "H":
            basic.showString("H", 50)
            serial.writeLine("GWCH")
            break
    }
}

radio.onReceivedBuffer(function (buf: Buffer){
    const head = buf.unpack("Bl")
    const key = String.fromCharCode(head[0])
    const id = head[1]
    if(id != control.deviceSerialNumber()){
        serial.writeLine(`GW: message not for me: ${id} != ${control.deviceSerialNumber()}`)
        return
    }
    if(key != "*"){
        return
    }
    const ikey = String.fromCharCode(buf.unpack("B", 5)[0])
    const from_id = radio.lastPacket.serial
    serial.writeLine(`GW: message for me: ${id} == ${control.deviceSerialNumber()}`)
    serial.writeLine(`GW: from: ${from_id}`)
    serial.writeLine(`GW: msg: ${ikey}`)
    switch(ikey){
        case "Q":
            serial.writeLine(`GWCQ${from_id}`)
            break
    }
})

serial.setRxBufferSize(128)
serial.setTxBufferSize(128)
basic.showString("GW", 50)
radio.setGroup(57)
radio.setTransmitPower(7)
radio.setTransmitSerialNumber(true)


