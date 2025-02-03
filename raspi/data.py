import serial
import re
import time
import csv
from datetime import datetime

class SerialManager():
    def __init__(self, port="/dev/ttyACM0", baud_rate=115200) -> None:
        self.ser = serial.Serial(port, baud_rate, timeout=3)
        
        self.ser.setDTR(False)
        time.sleep(1)
        self.ser.flushInput()
        self.ser.setDTR(True)
        time.sleep(2)
        
        self.log_file = f"logs/encoder_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(self.log_file, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'left_encoder', 'right_encoder'])

    
    def send_pwm(self, pwm: list[int], dirs: list[int]) -> None:
        pwm_vals = [[0, 0], [0, 0]]
        for k in range(2):
            if dirs[k] == 1:
                pwm_vals[k] = [pwm[k], 0]
            elif dirs[k] == -1:
                pwm_vals[k] = [0, pwm[k]]
            else:
                pwm_vals[k] = [0, 0]
        
        pwm_string = f"{pwm_vals[0][0]};{pwm_vals[0][1]};{pwm_vals[1][0]};{pwm_vals[1][1]}\n"
        pwm_as_bytes = str.encode(pwm_string) # convert string to bytes
        self.ser.write(pwm_as_bytes)
    
    
    def read_input(self) -> str:
        # flush input to get the latest data
        self.ser.flushInput()

        while True:
            line = self.ser.readline().decode("utf-8")
            
            if line and line[0] == 'l': # make shure to get complete data
                return line
    
    
    # serial string to l, r, x, y, t
    def extract_values(self, input_str: str) -> tuple[int, int, int, int, float]:
        pattern = r'l(-?\d+)r(-?\d+)x(-?\d+)y(-?\d+)t(-?\d*\.?\d*)'
        match = re.match(pattern, input_str)
        
        if not match:
            raise ValueError(f"Could not extract all values from string: {input_str}")
        
        l = int(match.group(1))  # Value for l
        r = int(match.group(2))  # Value for r
        x = int(match.group(3))  # Value for x
        y = int(match.group(4))  # Value for y
        t = float(match.group(5))  # Value for theta
        
        return l, r, x, y, t
    
    
    def get_pos(self) -> list[int, int, int, int, float]:
        serial_input = self.read_input() # get latest input
        l, r, x, y, theta = self.extract_values(serial_input) # extract x y theta from serial data
        
        self.log_data(l, r)

        # print(f'Arduino sent: Left Encoder:{l}, Right Encoder:{r}, x: {x}, y: {y}, theta: {theta}')
        return [l, r, x, y, theta]
    
    
    def reset_pos(self) -> None:
        reset_string = f"r\n"
        byte_string = str.encode(reset_string)
        self.ser.write(byte_string)
        
        
    def log_data(self, left, right) -> None:
        with open(self.log_file, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().timestamp(), left, right])