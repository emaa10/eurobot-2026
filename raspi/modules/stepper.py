# UNGETESTET, OHNE LOGGING

import serial

class Stepper:
    def __init__(self, port="/dev/serial/by-id/usb-Raspberry_Pi_Pico_45503571288B014-if00", baudrate=115200) -> None:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=3)

    def home(l: bool, m: bool, r:bool):
        if l:
            send("$HX\n")
        if m:
            send("$HY\n")
        if r:
            send("$HZ\n")

    def set_pos_mm(l: int = 0, m: int = 0, r: int = 0):
        send(f"G54 X{abs(l)} Y{abs(m)} R{abs(r)}\n")
        
    def reset():
        send("\x18")

    def send(command: str):
        byte_string = str.encode(str)
        ser.write(byte_string)

