from modules.servos import Servos
from modules.esp32 import ESP32
from time import sleep


class Gripper:
    def __init__(self, servos: Servos, esp32: ESP32):
        self.servos = servos
        self.esp32  = esp32

    def home(self):
        self.servos.pos_anfahren(True)
        sleep(1)
        self.esp32.stepper_home()
        sleep(8)
        self.esp32.stepper_set(15, 0, 200)
        sleep(1)
        self._pos_home()

    def _pos_home(self):
        self.servos.servo_plate_rotate(1)
        sleep(1)
        self.servos.grip_außen()
        self.servos.gripper_in()
        self.servos.servo_plate_grip(2)
        self.servos.servo_left_rotate(5)
        self.servos.servo_right_grip(3)
        self.servos.servo_flag(1)

    def anfahren(self, first_time: bool = False):
        """Servos auf Anfahrposition + Stepper in Position."""
        self.servos.pos_anfahren(first_time)
        sleep(0.3)
        self.esp32.stepper_set(0, 18, 0)

    def build_2er(self):
        self.esp32.stepper_set(0, 0, 0)
        sleep(0.4)
        self.servos.grip_cans()
        sleep(0.5)
        self.servos.gripper_out()
        sleep(0.5)
        self.esp32.stepper_set(140, 130, 140)
        sleep(1)
        self.servos.gripper_in()
        sleep(0.85)
        self.servos.servo_mitte_lift(2)

    def grip_one_layer(self):
        self.servos.servo_left_grip(2)
        self.servos.servo_right_grip(2)
        self.esp32.stepper_set(0, 0, 0)
        sleep(1)
        self.servos.servo_plate_grip(2)
        self.servos.servo_left_rotate(1)
        self.servos.servo_right_rotate(1)
        sleep(1)
        self.esp32.stepper_set(30, 30, 30)

    def build_one_layer(self):
        self.servos.gripper_in()
        sleep(1)
        self.esp32.stepper_set(30, 15, 30)
        self.servos.servo_mitte_grip(1)

    def grip_unten(self):
        self.esp32.stepper_set(0, 0, 0)
        self.servos.servo_plate_rotate(1)
        sleep(0.7)
        self.servos.servo_left_rotate(2)
        self.servos.servo_right_rotate(2)
        self.servos.servo_mitte_lift(1)
        self.servos.servo_mitte_grip(1)
        self.servos.servo_left_grip(1)
        self.servos.servo_right_grip(1)
        self.servos.servo_left_rotate(4)
        self.servos.servo_right_rotate(4)

    def lift_3er(self):
        self.servos.servo_plate_grip(1)
        sleep(0.3)
        self.servos.servo_plate_rotate(1)
        sleep(0.5)
        self.esp32.stepper_set(260, 0, 260)

    def release(self):
        self.servos.release_all()
