from modules.servos import Servos
from time import sleep


class Gripper:
    def __init__(self, servos: Servos):
        self.servos = servos

    def home(self):
        self.servos.home()
        sleep(1)

    def greifen(self):
        """Alle 4 Greifer schließen."""
        self.servos.alle_zu()

    def loslassen(self):
        """Alle 4 Greifer öffnen."""
        self.servos.alle_auf()

    def innen_greifen(self):
        self.servos.innen_zu()

    def aussen_greifen(self):
        self.servos.aussen_zu()
