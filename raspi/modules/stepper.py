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
        self.send(f"G54 X{abs(r)} Y{abs(m)} Z{abs(l)}\n")
        
    def reset(self):
        self.send("\x18")
        # wait(2)
        # self.ser = 

    def send(self, command: str):
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
            
    def anfahren(self):
        self.set_pos_mm(0, 50, 0)
        
    def down(self):
        self.set_pos_mm(0, 0, 0)
    
    def lift(self):
        self.set_pos_mm(140, 130, 140)
        
    def place3er(self):
        self.set_pos_mm(130, 0, 130)

def main():
    stepper = Stepper()
    
    time.sleep(1)
    
    # stepper.send('$Z')
    stepper.lift()
    # stepper.pos_wegfahren()
    stepper.get_output()
    
if __name__ == '__main__':
    main()