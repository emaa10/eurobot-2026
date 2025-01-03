import serial
import re
import time

class SerialManager():
    def __init__(self, port="/dev/ttyACM0", baud_rate=115200):
        self.ser = serial.Serial(port, baud_rate, timeout=3)
        
        self.ser.setDTR(False)
        time.sleep(1)
        self.ser.flushInput()
        self.ser.setDTR(True)
        time.sleep(2)

    # serial string to x, y, t
    def extract_values(self, input_str: str):
        # Find matches for l and r as ints
        match = re.search(r'l(\d+)r(\d+)', input_str)
        
        # Check if all matches are found
        if not match:
            raise ValueError(f"Could not extract all values from string: {input_str}")
        
        # Extract and convert to floats
        l = float(match.group(1))
        r = float(match.group(2))
        
        return [l, r]
    
    def send_pwm(self, pwm: list[int], dirs: list[int]):
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
    
    def get_pos(self) -> list[int]:
        serial_input = self.read_input() # get latest input
        l, r = self.extract_values(serial_input) # extract x y theta from serial data

        print(f'Arduino sent: Left Encoder:{l}, Right Encoder:{r}')
        return [l, r]
    
    def reset_pos(self):
        reset_string = f"r\n"
        byte_string = str.encode(reset_string)
        self.ser.write(byte_string)
    