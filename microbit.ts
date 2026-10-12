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
    for (let i = 0; i < 5; i++) {
        radio.sendBuffer(buf)
        control.waitMicros(100)
    }
    basic.clearScreen()
})
basic.showString("GW", 50)
radio.setGroup(57)
radio.setTransmitPower(7)
