import serial
import re
import time
import csv
from datetime import datetime
import logging

class SerialManager():
    def __init__(self, port="/dev/ttyACM1", baud_rate=115200) -> None:
        self.ser = serial.Serial(port, baud_rate, timeout=3)
        
        self.ser.setDTR(False)
        time.sleep(1)
        self.ser.flushInput()
        self.ser.setDTR(True)
        time.sleep(1)
        
        self.logger = logging.getLogger(__name__)
            
    def read_input(self) -> str:
        # flush input to get the latest data
        self.ser.flushInput()

        while True:
            line = self.ser.readline().decode("utf-8")
            
            if line and line[0] == 'p': # make shure to get complete data
                return line
    
    # serial string to x, y, t
    def extract_values(self, input_str: str) -> tuple[int, int, float]:
        str_list = input_str[1:].split(';')
        
        if not input_str.startswith('p') or not len(str_list) == 3:        
            return 0, 0, 0.0

        x = int(str_list[0])
        y = int(str_list[1])
        theta = int(str_list[2])
    
    def get_pos(self) -> tuple[int, int, float] | None:
        serial_input = self.read_input() # get latest input
        
        str_list = serial_input[1:].split(';')
        
        if not serial_input.startswith('p') or not len(str_list) == 3:        
            return None

        x = int(str_list[0])
        y = int(str_list[1])
        theta = float(str_list[2])
        
        return x, y, theta
    
    def reset_pos(self) -> None:
        reset_string = "r\n"
        byte_string = str.encode(reset_string)
        self.ser.write(byte_string)
        
    def set_pos(self, x: int, y: int, theta: int) -> None:
        set_string = f"s{x};{y};{theta}\n"
        byte_string = str.encode(set_string)
        self.ser.write(byte_string)
        
def main():
    serial_manager = SerialManager()
    
    while True:
        serial_manager.logger.info(serial_manager.read_input())
        
if __name__ == '__main__':
    main()