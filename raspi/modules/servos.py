from modules.STservo_sdk import *
from modules.STservo_sdk.sts import STS_TORQUE_ENABLE, STS_MODE
from time import time

BAUDRATE         = 1000000
STS_MOVING_SPEED = 3000
STS_MOVING_ACC   = 80

WINKER_STEPS = 1707  # 150° in Schritten (150/360 * 4096)


class Servos:
    PORT = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083059-if00"

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

    def write_servo_relative(self, id: int, delta: int):
        """Fährt relativ zur aktuellen Position um delta Schritte."""
        if self.check_time():
            return
        self.packet_handler.write1ByteTxRx(id, STS_MODE, 0)
        self.packet_handler.write1ByteTxRx(id, STS_TORQUE_ENABLE, 1)
        pos, result, _ = self.packet_handler.ReadPos(id)
        if result != 0:
            return
        self.packet_handler.WritePosEx(id, pos + delta, STS_MOVING_SPEED, STS_MOVING_ACC)

    # ── 4 Frontgreifer (von links nach rechts: ID 2, 1, 11, 9) ────────────

    def grip_links_aussen(self, pos: int):
        """ID 2 – ganz links. 1: auf, 2: zu"""
        match pos:
            case 1: self.write_servo(2, 1048)
            case 2: self.write_servo(2, 2000)

    def grip_links_innen(self, pos: int):
        """ID 1 – zweiter von links. 1: auf, 2: zu"""
        match pos:
            case 1: self.write_servo(1, 1500)
            case 2: self.write_servo(1, 2500)

    def grip_rechts_innen(self, pos: int):
        """ID 11 – zweiter von rechts. 1: auf, 2: zu"""
        match pos:
            case 1: self.write_servo(11, 1048)
            case 2: self.write_servo(11, 2100)

    def grip_rechts_aussen(self, pos: int):
        """ID 9 – ganz rechts. 1: auf, 2: zu"""
        match pos:
            case 1: self.write_servo(9, 1048)
            case 2: self.write_servo(9, 2048)

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

    # ── Lift-Modul (ID 3 = Lift A, ID 6 = Lift B) ────────────────────────
    LIFT_A = 3
    LIFT_B = 6
    LIFT_A_HOCH   = 0    # TODO: kalibrieren
    LIFT_A_RUNTER = 0    # TODO: kalibrieren
    LIFT_B_HOCH   = 0    # TODO: kalibrieren
    LIFT_B_RUNTER = 0    # TODO: kalibrieren

    def lift_hoch(self):
        self.write_servo(self.LIFT_A, self.LIFT_A_HOCH)
        self.write_servo(self.LIFT_B, self.LIFT_B_HOCH)

    def lift_runter(self):
        self.write_servo(self.LIFT_A, self.LIFT_A_RUNTER)
        self.write_servo(self.LIFT_B, self.LIFT_B_RUNTER)

    # ── Winker (2 unabhängige Servos) ─────────────────────────────────────
    # Winker 1 = ID 7 = linker Winker  (bestätigt)
    # Winker 2 = ID 8 = rechter Winker (bestätigt)
    # Beide drehen relativ ±150° (WINKER_STEPS), keine absoluten Positionen

    def winker1_runter(self):
        self.write_servo_relative(7, -WINKER_STEPS)  # 150° nach rechts/unten

    def winker1_hoch(self):
        self.write_servo_relative(7, +WINKER_STEPS)  # 150° zurück

    def winker2_runter(self):
        self.write_servo_relative(8, -WINKER_STEPS)  # 150° nach rechts/unten

    def winker2_hoch(self):
        self.write_servo_relative(8, +WINKER_STEPS)  # 150° zurück

    # ── Home-Position ──────────────────────────────────────────────────────

    def home(self):
        self.alle_auf()
        self.lift_runter()
