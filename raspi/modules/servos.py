from modules.STservo_sdk import *
from time import time, sleep

BAUDRATE         = 1000000
STS_MOVING_SPEED = 3000
STS_MOVING_ACC   = 80


class Servos:
    PORT = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083062-if00"

    def __init__(self, port: str = PORT):
        self.port_handler   = PortHandler(port)
        self.packet_handler = sts(self.port_handler)
        self.time_started   = 9999999999999999

        if not self.port_handler.openPort():
            raise RuntimeError(f"Servo port nicht gefunden: {port}")
        if not self.port_handler.setBaudRate(BAUDRATE):
            raise RuntimeError("Servo baudrate konnte nicht gesetzt werden")

    def check_time(self) -> bool:
        return self.time_started + 99 < time()

    def write_servo(self, id: int, goal_position: int):
        if self.check_time():
            return
        self.packet_handler.WritePosEx(id, goal_position, STS_MOVING_SPEED, STS_MOVING_ACC)

    # ── 4 Frontgreifer (von links nach rechts: ID 2, 1, 11, 9) ────────────

    def grip_links_aussen(self, pos: int):
        """ID 2 – ganz links. 1: auf, 2: zu"""
        match pos:
            case 1: self.write_servo(2, 100)
            case 2: self.write_servo(2, 630)

    def grip_links_innen(self, pos: int):
        """ID 1 – zweiter von links. 1: auf, 2: zu, 3: home"""
        match pos:
            case 1: self.write_servo(1, 4000)
            case 2: self.write_servo(1, 3450)
            case 3: self.write_servo(1, 3000)

    def grip_rechts_innen(self, pos: int):
        """ID 11 – zweiter von rechts. 1: auf, 2: zu (TODO: Positionen kalibrieren)"""
        match pos:
            case 1: self.write_servo(11, 3825)
            case 2: self.write_servo(11, 2500)

    def grip_rechts_aussen(self, pos: int):
        """ID 9 – ganz rechts. 1: auf, 2: zu (TODO: Positionen kalibrieren)"""
        match pos:
            case 1: self.write_servo(9, 1800)
            case 2: self.write_servo(9, 2800)

    # ── Kombinierte Greif-Aktionen ─────────────────────────────────────────

    def alle_auf(self):
        self.grip_links_aussen(1)
        self.grip_links_innen(1)
        self.grip_rechts_innen(1)
        self.grip_rechts_aussen(1)

    def alle_zu(self):
        self.grip_links_aussen(2)
        self.grip_links_innen(2)
        self.grip_rechts_innen(2)
        self.grip_rechts_aussen(2)

    def innen_zu(self):
        self.grip_links_innen(2)
        self.grip_rechts_innen(2)

    def aussen_zu(self):
        self.grip_links_aussen(2)
        self.grip_rechts_aussen(2)

    # ── Weiterer Mechanismus (IDs 3, 7, 10 – anpassen falls nötig) ────────

    def servo_mitte_lift(self, pos: int):
        """ID 3. 1: unten, 2: oben"""
        match pos:
            case 1: self.write_servo(3, 2850)
            case 2: self.write_servo(3, 3030)

    def servo_mitte_grip(self, pos: int):
        """ID 7. 1: auf, 2: zu"""
        match pos:
            case 1: self.write_servo(7, 3700)
            case 2: self.write_servo(7, 3200)

    def servo_arm_rotation(self, pos: int):
        """ID 10. 1: außen, 2: mitte, 3: innen, 4: unten, 5: home"""
        match pos:
            case 1: self.write_servo(10, 470)
            case 2: self.write_servo(10, 1300)
            case 3: self.write_servo(10, 1775)
            case 4: self.write_servo(10, 1825)
            case 5: self.write_servo(10, 2220)

    # ── Home-Position ──────────────────────────────────────────────────────

    def home(self):
        self.alle_auf()
        self.servo_mitte_lift(1)
        self.servo_mitte_grip(1)
        self.servo_arm_rotation(5)
