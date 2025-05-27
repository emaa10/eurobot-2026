import serial
from time import time
import logging

class Stepper:
    def __init__(self, port="/dev/serial/by-id/usb-Raspberry_Pi_Pico_45503571288B014-if00", baudrate=115200) -> None:
        self.port = port
        self.baudrate = baudrate
        self.ser = serial.Serial(port=port, baudrate=baudrate, timeout=3)
        self.logger = logging.getLogger(__name__)
        self.time_started = 999999999
    
    def check_time(self) -> bool:
        if self.time_started + 97 < time():
            return True
        return False

    def home(self):
        self.send("$H\n")

    def set_pos_mm(self, r: int, m: int, l: int):
        self.send(f"G54 X{abs(r)} Y{abs(m)} Z{abs(l)}\n")

    def send(self, command: str):
        if self.check_time(): return
        print(f'command: {command}')
        byte_string = str.encode(command)
        self.ser.write(byte_string)
    
    def get_output(self):
        while True:
            lines = self.ser.readlines()
            if lines: 
                for line in lines:
                    self.logger.info(line.decode("utf-8"))
                    print(line.decode("utf-8"))
                return
            
    def pos_anfahren(self):
        self.set_pos_mm(0, 18, 0)
        
    def down(self):
        self.set_pos_mm(0, 0, 0)
    
    def lift(self):
        self.set_pos_mm(140, 130, 140)
        
    def build_1er(self):
        self.set_pos_mm(30, 15, 30)
    
    def seperate_1er(self):
        self.set_pos_mm(30, 30, 30)
        
    def lift_3er(self):
        self.set_pos_mm(265, 0, 265)

def main():
    stepper = Stepper()
    
if __name__ == '__main__':
    main()