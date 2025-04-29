import serial
import time
import logging

class Pico():
    def __init__(self, port="/dev/serial/by-id/usb-Raspberry_Pi_Pico_E66118C4179D582D-if00", baud_rate=115200) -> None:
        self.ser = serial.Serial(port, baud_rate, timeout=1)
        
        self.ser.setDTR(False)
        time.sleep(1)
        self.ser.flushInput()
        self.ser.setDTR(True)
        time.sleep(1)
        
        self.logger = logging.getLogger(__name__)
            
    def get_status(self) -> str | None:
        # flush input to get the latest data
        self.ser.flushInput()

        line = self.ser.readline().decode("utf-8")
        
        if line:
            return line[:-2]
        
    def wait_for_ok(self):
        while True:
            status = self.get_status()
            if status == 'ok': 
                break
        
    def set_command(self, command: str, value: int) -> None:
        command_string = f"{command}{value}\n"
        byte_string = str.encode(command_string)
        self.ser.write(byte_string)
        
def main():
    serial_manager = Pico()
    
    serial_manager.set_command('h', 2000)
        
if __name__ == '__main__':
    main()