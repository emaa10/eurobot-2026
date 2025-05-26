from modules.STservo_sdk import * 

BAUDRATE                    = 1000000           # STServo default baudrate : 1000000
STS_MOVING_SPEED            = 2400          # SCServo moving speed
STS_MOVING_ACC              = 50            # SCServo moving acc

class Servos:
    def __init__(self, port = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083062-if00") -> None:
        self.port_handler = PortHandler(port)
        self.packet_handler = sts(self.port_handler)

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

    def write_servo(self, id, goal_position):
        """
        writes servo with id to goal pos
        """
        self.packet_handler.WritePosEx(id, goal_position, STS_MOVING_SPEED, STS_MOVING_ACC)

    def servo_mitte_lift(self, pos: int):
        """
        1: unten, 2: oben
        """
        value = 0
        match pos:
            case 1: value = 2900
            case 2: value = 3030
        self.write_servo(3, value)

    def servo_mitte_grip(self, pos: int):
        """
        1: auf, 2: zu
        """
        value = 0 
        match pos:
            case 1: value = 3700
            case 2: value = 3250
            case _: value = 3600

        self.write_servo(7, value)

    def servo_right_rotate(self, pos: int):
        """
        1: außen, 2: mitte, 3: innen
        """
        value = 0 
        if pos == 1: value = 3825
        elif pos == 2: value = 3040
        else: value = 2500
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
        1: auf, 2: zu
        """
        value = 0 
        if pos == 1: value = 3950 #3750
        else: value = 3500 #3650
        self.write_servo(1, value)

    def servo_left_grip(self, pos: int):
        """
        1: auf, 2: zu
        """
        value = 0 
        if pos == 1: value = 150 #350
        else: value = 630 #650
        self.write_servo(2, value)

    def servo_left_rotate(self, pos: int):
        """
        1: außen, 2: mitte, 3: innen
        """
        value = 0 
        if pos == 1: value = 180
        elif pos == 2: value = 900
        else: value = 1460
        self.write_servo(10, value)

    def servo_plate_grip(self, pos: int):
        """
        1: auf, 2: zu
        """
        value = 0 
        if pos == 1: value = 950
        else: value = 1600
        self.write_servo(8, value)
        
    def pos_anfahren(self):
        """
        servos auf anfahren setzen
        """
        self.servo_left_rotate(2)
        self.servo_right_rotate(2)
        self.servo_mitte_lift(1)
        self.servo_mitte_grip(1)
        self.servo_left_grip(1)
        self.servo_right_grip(1)
        self.servo_plate_rotate(2)
        self.servo_plate_grip(1)
        
    def grip_cans(self):
        """
        servos auf greifen
        """
        self.servo_mitte_grip(2)
        self.servo_left_grip(2)
        self.servo_right_grip(2)
        self.servo_plate_grip(2)
        time.sleep(1)
        self.servo_left_rotate(1)
        self.servo_right_rotate(1)
        
    def grip_one_layer(self):
        self.servo_left_grip(2)
        self.servo_right_grip(2)
        self.servo_left_rotate(1)
        self.servo_right_rotate(1)
    
    def cans_in(self):
        self.servo_left_rotate(3)
        self.servo_right_rotate(3)

    def pos_wegfahren(self):
        self.servo_mitte_lift(2)
        
    def place_1er(self, num: int):
        if num == 1:
            self.servo_mitte_lift(1)
            time.sleep(0.3)
            self.servo_mitte_grip(1)
        else:
            self.servo_plate_grip(1)
            self.servo_left_grip(1)
            self.servo_right_grip(1)
        
        
    def place_2er(self):
        self.servo_mitte_lift(1)
        time.sleep(0.3)
        self.servo_mitte_grip(1)
        self.servo_left_grip(1)
        self.servo_right_grip(1)
        self.servo_plate_grip(1)
        time.sleep(0.3)
        self.servo_plate_rotate(1)
        
    def grip_unten(self):
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

    def start_position(self):
        self.servo_left_grip(2)
        self.servo_right_grip(2)

        self.servo_left_rotate(3)
        self.servo_right_rotate(3)

        self.servo_mitte_grip(1)
        
        self.servo_plate_rotate(1)
        
def main():
    servos = Servos()
    servos.servo_mitte_lift(1)
    
if __name__ == '__main__':
    main()