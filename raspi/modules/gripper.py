from modules.servos import Servos
from time import sleep


class Gripper:
    def __init__(self, servos: Servos):
        self.servos = servos

    def home(self):
        self.servos.home()
        sleep(1)

    # ── Greifer ───────────────────────────────────────────────────────────

    def driving(self):
        self.servos.alle_driving()

    def greifen(self):
        self.servos.alle_zu()

    def loslassen(self):
        self.servos.alle_auf()

    def innen_greifen(self):
        self.servos.innen_zu()

    def aussen_greifen(self):
        self.servos.aussen_zu()

    # ── Lift ──────────────────────────────────────────────────────────────

    def lift_hoch(self):
        self.servos.lift_hoch()

    def lift_runter(self):
        self.servos.lift_runter()

    # ── Winker ────────────────────────────────────────────────────────────

    def winker(self, n: int, hoch: bool):
        """n=1 oder n=2, hoch=True/False."""
        if n == 1:
            self.servos.winker1_hoch() if hoch else self.servos.winker1_runter()
        else:
            self.servos.winker2_hoch() if hoch else self.servos.winker2_runter()
