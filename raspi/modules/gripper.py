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
        self.servos.alle_auf()
        self.servos.lift_hoch()

    def lift_runter(self):
        self.servos.lift_runter()

    # ── Winker ────────────────────────────────────────────────────────────

    def winker(self, side: str, hoch: bool):
        """side='r' (rechts, ID 7) oder 'l' (links, ID 8), hoch=True/False."""
        if side == 'r':
            self.servos.winker_rechts_hoch() if hoch else self.servos.winker_rechts_runter()
        else:
            self.servos.winker_links_hoch()  if hoch else self.servos.winker_links_runter()
