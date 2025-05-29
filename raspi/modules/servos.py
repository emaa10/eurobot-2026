from modules.STservo_sdk import * 
from time import time, sleep

BAUDRATE                    = 1000000           # STServo default baudrate : 1000000
STS_MOVING_SPEED            = 3000          # SCServo moving speed
STS_MOVING_ACC              = 80            # SCServo moving acc

class Servos:
    def __init__(self, port = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083062-if00") -> None:
        self.port_handler = PortHandler(port)
        self.packet_handler = sts(self.port_handler)
        
        self.time_started = 9999999999999999

        # Open port
        if self.port_handler.openPort():
            print("Succeeded to open the port")
        else:
            print("Failed to open the port")
            quit()

        # Set port baudrate
        if self.port_handler.setBaudRate(BAUDRATE):
            print("Succeeded to change the baudrate")
        else:
            print("Failed to change the baudrate")
            quit()
    
    def check_time(self) -> bool:
        if self.time_started + 99 < time():
            return True
        return False

    def write_servo(self, id, goal_position):
        """
        writes servo with id to goal pos
        """
        if self.check_time(): return
        self.packet_handler.WritePosEx(id, goal_position, STS_MOVING_SPEED, STS_MOVING_ACC)

    def servo_mitte_lift(self, pos: int):
        """
        1: unten, 2: oben
        """
        value = 0
        match pos:
            case 1: value = 2850
            case 2: value = 3030
            
        self.write_servo(3, value)

    def servo_mitte_grip(self, pos: int):
        """
        1: auf, 2: zu
        """
        value = 0 
        match pos:
            case 1: value = 3700
            case 2: value = 3200
            case _: value = 3600

        self.write_servo(7, value)

    def servo_right_rotate(self, pos: int):
        """
        1: außen, 2: mitte, 3: innen, 4: grip unten
        """
        value = 0 
        match pos:
            case 1: value = 3825
            case 2: value = 2980
            case 3: value = 2500
            case 4: value = 2450
            
        self.write_servo(11, value)

    def servo_plate_rotate(self, pos: int):
        """
        1: oben, 2: unten
        """
        value = 0 
        if pos == 1: value = 1800
        else: value = 2800
        self.write_servo(9, value)

    def servo_right_grip(self, pos: int):
        """
        1: auf, 2: zu, 3: home pos
        """
        value = 0 
        match pos:
            case 1: value = 4000
            case 2: value = 3450
            case 3: value = 3000
        self.write_servo(1, value)

    def servo_left_grip(self, pos: int):
        """
        1: auf, 2: zu
        """
        value = 0 
        match pos:
            case 1: value = 100
            case 2: value = 630

        self.write_servo(2, value)

    def servo_left_rotate(self, pos: int):
        """
        1: außen, 2: mitte, 3: innen, 4: grip unten, 5: home pos
        """
        value = 0 
        match pos:
            case 1: value = 470
            case 2: value = 1300
            case 3: value = 1775
            case 4: value = 1825
            case 5: value = 2220
        self.write_servo(10, value)

    def servo_plate_grip(self, pos: int):
        """
        1: auf, 2: zu
        """
        value = 0 
        if pos == 1: value = 950
        else: value = 1700
        self.write_servo(8, value)
    
    def servo_flag(self, pos: int):
        """
        1: oben, 2: unten
        """
        value = 0 
        if pos == 1: value = 2200
        else: value = 950
        self.write_servo(6, value)
    
    def pos_anfahren(self, first_time = False):
        """
        servos auf anfahren setzen
        """
        self.servo_left_rotate(2)
        self.servo_right_rotate(2)
        if first_time: sleep(0.3)
        self.servo_plate_rotate(2)
        self.servo_plate_grip(1)
        self.servo_mitte_lift(1)
        self.servo_mitte_grip(1)
        self.servo_left_grip(1)
        self.servo_right_grip(1)
        self.servo_flag(1)
        
    
    def grip_cans(self):
        """
        servos auf greifen
        """
        self.servo_mitte_grip(2)
        self.servo_left_grip(2)
        self.servo_right_grip(2)
        self.servo_plate_grip(2)
    
    def gripper_out(self):
        self.servo_left_rotate(1)
        self.servo_right_rotate(1)      
    
    def gripper_in(self):
        self.servo_left_rotate(3)
        self.servo_right_rotate(3)
    
    def grip_außen(self):
        self.servo_left_grip(2)
        self.servo_right_grip(2)
        
    def release_außen(self):
        self.servo_left_grip(1)
        self.servo_right_grip(1)
        
    def release_all(self):
        self.servo_mitte_lift(1)
        self.servo_left_grip(1)
        self.servo_right_grip(1)
        self.servo_mitte_grip(1)
        self.servo_plate_grip(1)
        
def main():
    servos = Servos()
    servos.servo_mitte_lift(1)
    
if __name__ == '__main__':
    main()