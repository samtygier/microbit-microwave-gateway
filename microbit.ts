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

basic.showString("GW", 50)
radio.setGroup(57)
radio.setTransmitPower(7)
