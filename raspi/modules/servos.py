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
        self.packet_handler.WritePosEx(id, goal_position, STS_MOVING_SPEED, STS_MOVING_ACC)

    # 1: oben, 2: unten
    def servo_mitte_lift(self, pos: int):
        value = 0 
        if pos == 1: value = 4000
        else: value = 3900
        self.write_servo(3, value)

    # 1: auf, 2: zu
    def servo_mitte_grip(self, pos: int):
        value = 0 
        if pos == 1: value = 3700
        else: value = 3300
        self.write_servo(7, value)

    # 1: außen, 2: mitte, 3: innen
    def servo_right_rotate(self, pos: int):
        value = 0 
        if pos == 1: value = 3825
        elif pos == 2: value = 3100
        else: value = 2500
        self.write_servo(11, value)

    # 1: oben, 2: unten
    def servo_plate_rotate(self, pos: int):
        value = 0 
        if pos == 1: value = 1800
        else: value = 2800
        self.write_servo(9, value)

    # 1: auf, 2: zu
    def servo_right_grip(self, pos: int):
        value = 0 
        if pos == 1: value = 800
        else: value = 410
        self.write_servo(1, value)

    # 1: auf, 2: zu
    def servo_left_grip(self, pos: int):
        value = 0 
        if pos == 1: value = 100
        else: value = 630
        self.write_servo(2, value)

    # 1: außen, 2: mitte, 3: innen
    def servo_left_rotate(self, pos: int):
        value = 0 
        if pos == 1: value = 1350
        elif pos == 2: value = 1975
        else: value = 2625
        self.write_servo(10, value)

    # 1: auf, 2: zu
    def servo_plate_grip(self, pos: int):
        value = 0 
        if pos == 1: value = 1000
        else: value = 1550
        self.write_servo(8, value)