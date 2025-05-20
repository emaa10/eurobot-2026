import serial
import time
import logging

class Stepper:
    def __init__(self, port="/dev/serial/by-id/usb-Raspberry_Pi_Pico_45503571288B014-if00", baudrate=115200) -> None:
        self.port = port
        self.baudrate = baudrate
        self.ser = serial.Serial(port=port, baudrate=baudrate, timeout=3)
        self.logger = logging.getLogger(__name__)
    

    def home(self, r: bool = True, m: bool = True, l:bool = True):  # funktioniert (da auch im)
        if r:
            self.send("$HX\n")
        if m:
            self.send("$HY\n")
        if l:
            self.send("$HZ\n")

    def set_pos_mm(self, r: int, m: int, l: int):           #funktioniert im Moment nicht, output vom board müsste in den log für richtiges bugfixing
        self.send(f"G54 X{abs(r)} Y{abs(m)} R{abs(l)}\n")
        
    def reset(self):
        self.send("\x18")
        # wait(2)
        # self.ser = 

    def send(self, command: str):
        self.ser.flushInput()
        byte_string = str.encode(command)
        self.ser.write(byte_string)
    
    def get_output(self):
        while True:
            lines = self.ser.readlines()
            if lines: 
                for line in lines:
                    print(line.decode("utf-8"))
                return

def main():
    stepper = Stepper()
    stepper.set_pos_mm(100, 100, 100)
    stepper.get_output()