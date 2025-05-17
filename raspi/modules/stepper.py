# UNGETESTET, OOP u. LOGGING wahrscheinlich optional, ansonsten wie arduino_com.py

import serial


PORT = "/dev/serial/by-id/usb-Raspberry_Pi_Pico_45503571288B014-if00"
BAUD_RATE = 115200


ser = serial.Serial(port=PORT, baudrate=BAUD_RATE, timeout=3)

def home(l: bool, m: bool, r:bool):
    if l:
        send("$HX\n")
    if m:
        send("$HY\n")
    if r:
        send("$HZ\n")

def set_pos_mm(l: int = 0, m: int = 0, r: int = 0):
    send(f"G54 X{abs(l)} Y{abs(m)} R{abs(r)}")
    
def reset():
    send("\x18")

def send(command: str):
    byte_string = str.encode(str)
    ser.write(byte_string)

