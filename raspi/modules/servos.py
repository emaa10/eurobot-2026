# Identisch zu letztem Jahr – gleiche Hardware (STServo USB)
# STservo_sdk Ordner aus 2024-25 kopieren: raspi/modules/STservo_sdk/

from modules.STservo_sdk import *
from time import time, sleep

BAUDRATE         = 1000000
STS_MOVING_SPEED = 3000
STS_MOVING_ACC   = 80


class Servos:
    def __init__(self, port: str = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083062-if00"):
        self.port_handler   = PortHandler(port)
        self.packet_handler = sts(self.port_handler)
        self.time_started   = 9999999999999999

        if not self.port_handler.openPort():
            print("Failed to open servo port")
            quit()
        if not self.port_handler.setBaudRate(BAUDRATE):
            print("Failed to set servo baudrate")
            quit()

    def check_time(self) -> bool:
        return self.time_started + 99 < time()

    def write_servo(self, id: int, goal_position: int):
        if self.check_time():
            return
        self.packet_handler.WritePosEx(id, goal_position, STS_MOVING_SPEED, STS_MOVING_ACC)

    def servo_mitte_lift(self, pos: int):
        """1: unten, 2: oben"""
        match pos:
            case 1: self.write_servo(3, 2850)
            case 2: self.write_servo(3, 3030)

    def servo_mitte_grip(self, pos: int):
        """1: auf, 2: zu"""
        match pos:
            case 1: self.write_servo(7, 3700)
            case 2: self.write_servo(7, 3200)
            case _: self.write_servo(7, 3600)

    def servo_right_rotate(self, pos: int):
        """1: außen, 2: mitte, 3: innen, 4: grip unten"""
        match pos:
            case 1: self.write_servo(11, 3825)
            case 2: self.write_servo(11, 2980)
            case 3: self.write_servo(11, 2500)
            case 4: self.write_servo(11, 2450)

    def servo_plate_rotate(self, pos: int):
        """1: oben, 2: unten"""
        self.write_servo(9, 1800 if pos == 1 else 2800)

    def servo_right_grip(self, pos: int):
        """1: auf, 2: zu, 3: home"""
        match pos:
            case 1: self.write_servo(1, 4000)
            case 2: self.write_servo(1, 3450)
            case 3: self.write_servo(1, 3000)

    def servo_left_grip(self, pos: int):
        """1: auf, 2: zu"""
        match pos:
            case 1: self.write_servo(2, 100)
            case 2: self.write_servo(2, 630)

    def servo_left_rotate(self, pos: int):
        """1: außen, 2: mitte, 3: innen, 4: grip unten, 5: home"""
        match pos:
            case 1: self.write_servo(10, 470)
            case 2: self.write_servo(10, 1300)
            case 3: self.write_servo(10, 1775)
            case 4: self.write_servo(10, 1825)
            case 5: self.write_servo(10, 2220)

    def servo_plate_grip(self, pos: int):
        """1: auf, 2: zu"""
        self.write_servo(8, 800 if pos == 1 else 1700)

    def servo_flag(self, pos: int):
        """1: oben, 2: unten"""
        self.write_servo(6, 2200 if pos == 1 else 950)

    def pos_anfahren(self, first_time: bool = False):
        self.servo_left_rotate(2)
        self.servo_right_rotate(2)
        if first_time:
            sleep(0.3)
        self.servo_plate_rotate(2)
        self.servo_plate_grip(1)
        self.servo_mitte_lift(1)
        self.servo_mitte_grip(1)
        self.servo_left_grip(1)
        self.servo_right_grip(1)
        self.servo_flag(1)

    def grip_cans(self):
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
