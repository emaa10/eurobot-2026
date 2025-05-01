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
        
    def set_right_stepper(self, pos: int):
        self.set_command("a", pos)

    def set_mid_stepper(self, pos: int):
        self.set_command("b", pos)

    # 1: up, 2: down
    def set_left_servo(self, command: int):
        if(command == 1):
            self.set_command("r", 0)
        else:
            self.set_command("r", 180)
                        
    # 1: fully open, 2: grip plate, 3: collision avoidance, 4: closed
    def set_plate_gripper(self, command: int):
        if(command == 1): self.set_command("s", 180)
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
            self.set_command("v", 20)
        else:
            self.set_command("v", 80)

    # 1: outwards, 2: inwards, 3: deposit, 4: mid
    def servo_rotate_right(self, command: int):
        if(command == 1): self.set_command("w", 5)
        elif(command == 2): self.set_command("w", 170)
        elif(command == 3): self.set_command("w", 155)
        elif(command == 4): self.set_command("w", 100)

    # 1: closed, 2: open
    def set_grip_left(self, command: int):
        if(command == 1):
            self.set_command("y", 85)
        else:
            self.set_command("y", 30)

    # 1: outwards, 2: inwards, 3: deposit, 4: mid
    def servo_rotate_left(self, command: int):
        if(command == 1): self.set_command("x", 115)
        elif(command == 2): self.set_command("x", 5)
        elif(command == 3): self.set_command("x", 5)
        elif(command == 4): self.set_command("x", 75)

    def home_pico(self):
        self.set_command("h", 0)

    def emergency_stop(self):
        self.set_command("e", 0)

    # 1: slightly lifted, 2: more lifted, 3: on the plate, 4: on top
    def setRightStepper(self, position: int):
        if(position == 1): self.set_right_stepper(1)
        elif(position == 2): self.set_right_stepper(2)
        elif(position == 3): self.set_right_stepper(3)
        elif(position == 4): self.set_right_stepper(4)

    # 1-3: plates, 4: on top
    def setMiddleStepper(self, position: int):
        if(position == 1): self.set_mid_stepper(1)
        elif(position == 2): self.set_mid_stepper(2)
        elif(position == 3): self.set_mid_stepper(3)
        elif(position == 4): self.set_mid_stepper(4)
        
def main():
    serial_manager = Pico()
    
    # serial_manager.set_command('b', 1000)
    # serial_manager.set_command('s', 0)
    
    # serial_manager.set_command('s', 130)
    # serial_manager.set_command('h', 0)
    # serial_manager.wait_for_ok()
    # print('done')
        
if __name__ == '__main__':
    main()