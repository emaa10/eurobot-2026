import time
from modules.STservo_sdk import *
from modules.STservo_sdk.sts import STS_TORQUE_ENABLE, STS_MODE

BAUDRATE         = 1000000
STS_MOVING_SPEED = 3000
STS_MOVING_ACC   = 80

WINKER_STEPS = 1707  # 150° in Schritten (150/360 * 4096)


class Servos:
    PORT = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083059-if00"
    ALL_IDS = [1, 2, 3, 6, 7, 8, 9, 11]

    def __init__(self, port: str = PORT):
        self.port_handler   = PortHandler(port)
        self.packet_handler = sts(self.port_handler)
        if not self.port_handler.openPort():
            raise RuntimeError(f"Servo port nicht gefunden: {port}")
        if not self.port_handler.setBaudRate(BAUDRATE):
            raise RuntimeError("Servo baudrate konnte nicht gesetzt werden")
        self.detach_all()

    def write_servo(self, id: int, goal_position: int):
        self.packet_handler.WritePosEx(id, goal_position, STS_MOVING_SPEED, STS_MOVING_ACC)

    def write_servo_relative(self, id: int, delta: int):
        self.packet_handler.write1ByteTxRx(id, STS_MODE, 0)
        self.packet_handler.write1ByteTxRx(id, STS_TORQUE_ENABLE, 1)
        pos, result, _ = self.packet_handler.ReadPos(id)
        if result != 0:
            return
        self.packet_handler.WritePosEx(id, pos + delta, STS_MOVING_SPEED, STS_MOVING_ACC)

    def detach_all(self):
        """Torque aller Servos deaktivieren (detach)."""
        for sid in self.ALL_IDS:
            self.packet_handler.write1ByteTxRx(sid, STS_TORQUE_ENABLE, 0)

    def attach_all(self):
        """Torque aller Servos nacheinander aktivieren (attach)."""
        for sid in self.ALL_IDS:
            self.packet_handler.write1ByteTxRx(sid, STS_TORQUE_ENABLE, 1)
            time.sleep(0.1)

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

    def alle_driving(self):
        """Mittelposition zwischen auf und zu – für Fahrt."""
        self.write_servo(2,  1524)  # (1048+2000)//2
        self.write_servo(1,  2000)  # (1500+2500)//2
        self.write_servo(11, 1574)  # (1048+2100)//2
        self.write_servo(9,  1548)  # (1048+2048)//2

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
    # Winker 1 = ID 7 = linker Winker
    # Winker 2 = ID 8 = rechter Winker
    WINKER1_OBEN   = 2012
    WINKER1_UNTEN  = 3473
    WINKER2_OBEN   = 980
    WINKER2_UNTEN  = 1958

    def winker1_runter(self):
        self.write_servo(7, self.WINKER1_UNTEN)

    def winker1_hoch(self):
        self.write_servo(7, self.WINKER1_OBEN)

    def winker2_runter(self):
        self.write_servo(8, self.WINKER2_UNTEN)

    def winker2_hoch(self):
        self.write_servo(8, self.WINKER2_OBEN)

    # ── Home-Position ──────────────────────────────────────────────────────

    def home(self):
        self.alle_auf()
        self.lift_runter()
        self.winker2_hoch()
