import serial
import time
import logging
from gpiozero import AngularServo

class Pico():
    def __init__(self, port="/dev/serial/by-id/usb-Raspberry_Pi_Pico_503558607AD3331F-if00", baud_rate=115200) -> None:
        self.ser = serial.Serial(port, baud_rate, timeout=1)
        
        self.ser.setDTR(False)
        time.sleep(1)
        self.ser.flushInput()
        self.ser.setDTR(True)
        time.sleep(1)
        
        self.logger = logging.getLogger(__name__)
        
        self.servo_rotate_left = AngularServo(12, min_pulse_width=0.0006, max_pulse_width=0.0023)
            
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

    # 1: up, 2: down
    def set_left_servo(self, command: int):
        if(command == 1):
            self.set_command("r", 0)
        else:
            self.set_command("r", 180)
                        
    # 1: fully open, 2: grip plate, 3: collision avoidance, 4: closed
    def set_plate_gripper(self, command: int):
        if(command == 1): self.set_command("s", 175)
        elif(command == 2): self.set_command("s", 120)
        elif(command == 3): self.set_command("s", 130)
        elif(command == 4): self.set_command("s", 0)

    # 1: up, 2: down
    def set_drive_flag(self, command: int):
        if(command == 1):
            self.set_command("t", 20)
        else:
            self.set_command("t", 165)

    # 1: closed, 2: open
    def set_grip_right(self, command: int):
        if(command == 1):
            self.set_command("v", 55)
        elif(command == 2):
            self.set_command("v", 30)
        elif(command == 3):
            self.set_command("v", 50)

    # 1: closed, 2: open
    def set_grip_left(self, command: int):
        if(command == 1):
            self.set_command("y", 80)
        elif(command == 2):
            self.set_command("y", 20)
        elif(command == 3):
            self.set_command("y", 75)
            
    # 1: outwards, 2: inwards, 3: deposit, 4: mid
    def set_servo_rotate_right(self, command: int):
        if(command == 1): self.set_command("w", 5)
        elif(command == 2): self.set_command("w", 170)
        elif(command == 3): self.set_command("w", 155)
        elif(command == 4): self.set_command("w", 100)
        elif(command == 5): self.set_command("w", 60)

    # 1: outwards, 2: inwards, 3: deposit, 4: mid
    def set_servo_rotate_left(self, command: int):
        if(not self.servo_rotate_left_attached): 
            self.servo_rotate_left = AngularServo(12, min_pulse_width=0.0006, max_pulse_width=0.0023)
        if(command == 1): self.servo_rotate_left.angle = 80
        elif(command == 2): self.servo_rotate_left.angle = -65
        elif(command == 3): self.servo_rotate_left.angle = 50
        elif(command == 4): self.servo_rotate_left.angle = 40
        time.sleep(0.5)
        self.servo_rotate_left.detach()
        self.servo_rotate_left = None
        

    def emergency_stop(self):
        self.set_command("e", 0)
        self.servo_rotate_left.detach()
        self.servo_rotate_left = None

    # 1: slightly lifted, 2: more lifted, 3: on the plate, 4: on top
    def set_right_stepper(self, position: int):
        self.set_command('a', position)

    # 1-3: plates, 4: on top
    def set_middle_stepper(self, position: int):
        self.set_command('b', position)
        
    def collission_free_sevors(self):
        self.set_left_servo(2)
        time.sleep(0.2)
        self.set_plate_gripper(3)
        time.sleep(0.2)
        self.set_drive_flag(1)
        time.sleep(0.2)
        self.set_grip_right(3)
        time.sleep(0.2)
        self.set_grip_left(3)
        time.sleep(0.2)
        self.set_servo_rotate_right(5)
        time.sleep(0.2)
        self.set_servo_rotate_left(1)
        
    def position_sevors(self):
        self.set_plate_gripper(4)
        self.set_servo_rotate_right(2)
        self.set_servo_rotate_left(2)
        
    def home_pico(self):
        self.collission_free_sevors()
        self.set_command("h", 0)
        self.wait_for_ok()
        self.position_sevors()
        time.sleep(0.5)
        
def main():
    serial_manager = Pico()
    time.sleep(1)

    # serial_manager.set_command('s', 0)
    
    # serial_manager.set_command('s', 130)
    # serial_manager.set_command('h', 0)
    # serial_manager.wait_for_ok()
    # print('done')
        
if __name__ == '__main__':
    main()