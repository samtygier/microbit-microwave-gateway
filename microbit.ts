serial.onDataReceived(serial.delimiters(Delimiters.NewLine), function () {
    basic.showLeds(`
        # . . . .
        . . . . .
        . . . . .
        . . . . .
        . . . . .
        `)
    const message = serial.readUntil(serial.delimiters(Delimiters.NewLine))
    const buf = Buffer.fromHex(message)
    radio.sendBuffer(buf)
    basic.clearScreen()
})
basic.showString("GW", 50)
radio.setGroup(57)
radio.setTransmitPower(7)
