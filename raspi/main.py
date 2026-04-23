"""
Eurobot 2026 – Hauptprogramm

Starten:
    python3 main.py              # interaktives Menü
    python3 main.py 1            # Taktik 1, Startpos 1
    python3 main.py 2 3          # Taktik 2, Startpos 3

Ablauf:
    1. Team-Farbe von GPIO lesen
    2. Taktik wählen (Menü oder Argument)
    3. Homing (Wand-Kalibrierung + Greifer-Home)
    4. Auf Zugschnur warten (GPIO 22)
    5. Taktik ausführen (99 s Spielzeit)
"""

import sys
import asyncio
import RPi.GPIO as GPIO
import logging
import signal
from time import time, sleep

from modules.task import Task
from modules.camera import Camera
from modules.esp32 import ESP32
from modules.servos import Servos
from modules.gripper import Gripper
from modules.lidar import Lidar

PIN_PULLCORD    = 22   # Pull-Up; LOW = Schnur drin, HIGH-Flanke = Start
PIN_TEAM_SELECT = 17   # Pull-Up; LOW = Blau, HIGH = Gelb

LOG_FILE = '/home/eurobot/eurobot-2026/raspi/eurobot.log'


# ── Taktik-Bibliothek (Blau-Koordinaten; Task spiegelt für Gelb) ──────────
TACTICS = {
    1: [['hg', 'hm', 'dd1000']],   # Test: Homing + 1 m vorwärts
    2: [['hg', 'hm', 'dd1000']],
    3: [['hg', 'hm', 'dd1000']],
    4: [['hg', 'hm', 'dd1000']],
}

# Startpositionen – nur genutzt wenn 'hm' NICHT in der Taktik
START_POSITIONS = {
    1: [150,  1800, 180],
    2: [600,  1800, 180],
    3: [1050, 1800, 180],
}


class Robot:
    def __init__(self, tactic_num: int, start_pos: int):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_PULLCORD,    GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_TEAM_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                            format='%(asctime)s %(levelname)s %(message)s')
        self.logger = logging.getLogger(__name__)

        self.color = 'blue' if GPIO.input(PIN_TEAM_SELECT) == GPIO.LOW else 'yellow'
        self.log(f"Team: {self.color}  Taktik: {tactic_num}  Startpos: {start_pos}")

        self.esp32   = ESP32()
        self.servos  = Servos()
        self.gripper = Gripper(self.servos)
        self.lidar   = Lidar()
        self.camera  = Camera()

        if not self.lidar.start_scanning():
            self.log("Warning: Lidar nicht gestartet")
        self.camera.start()

        tactic = TACTICS[tactic_num]
        has_hm = any('hm' in step for step in tactic[0])

        self.task = Task(self.esp32, self.camera, self.gripper, tactic, self.color)

        if not has_hm:
            x, y, theta = START_POSITIONS[start_pos]
            if self.color == 'yellow':
                x = 3000 - x
                theta = int((180 - theta) % 360)
            self.esp32.set_pos(x, y, theta)

    def log(self, msg: str):
        print(msg)
        self.logger.info(msg)

    def wait_for_pullcord(self):
        self.log("Warte auf Zugschnur …")
        while GPIO.input(PIN_PULLCORD) == GPIO.LOW:
            sleep(0.05)
        self.log("Zugschnur gezogen – Spiel startet!")

    # ── Drive-Wrapper (direkt nutzbar aus Taktik-Code) ────────────────────

    async def drive(self, mm: int):
        await self.esp32.drive_distance(mm)

    async def turn(self, deg: float):
        await self.esp32.turn_angle(deg)

    async def turn_to(self, deg: float):
        await self.esp32.turn_to(deg)

    async def drive_to(self, x: float, y: float):
        await self.esp32.drive_to(x, y)

    async def drive_to_point(self, x: float, y: float, theta: float):
        await self.esp32.drive_to_point(x, y, theta)

    async def stop(self):
        await self.esp32.set_stop()

    # ── Spielablauf ───────────────────────────────────────────────────────

    async def run(self):
        asyncio.create_task(self._camera_loop())
        asyncio.create_task(self._lidar_loop())

        # Taktik ausführen (Schritt für Schritt)
        t = time()
        self.esp32.time_started  = t
        self.servos.time_started = t

        while True:
            self.task = await self.task.run()
            if not self.task:
                self.log("Taktik abgeschlossen")
                break

        await self.stop()
        self.log("Fertig.")

    async def _camera_loop(self):
        while True:
            tags = self.camera.getTag()
            if tags:
                for tag in tags:
                    self.log(f"ArUco {tag.id}: {tag.horizontal_angle:.1f}° {tag.distance:.0f}mm")
            await asyncio.sleep(0.5)

    async def _lidar_loop(self):
        while True:
            if not self.lidar.is_running():
                self.log("Warning: Lidar-Thread nicht aktiv")
            await asyncio.sleep(5)

    def cleanup(self):
        self.lidar.stop()
        GPIO.cleanup()


# ── Taktik-Auswahl ────────────────────────────────────────────────────────

def select_tactic() -> tuple[int, int]:
    """Interaktives Menü wenn keine CLI-Argumente übergeben."""
    print("\n── Eurobot 2026 ──────────────────────────────")
    print("Taktiken:")
    for k in TACTICS:
        print(f"  {k}: {TACTICS[k]}")
    print()
    try:
        t = int(input("Taktik-Nummer: ").strip())
        p = int(input("Startposition (1-3): ").strip())
    except (ValueError, EOFError):
        print("Ungültige Eingabe – Taktik 1, Pos 1 wird verwendet")
        return 1, 1
    return t, p


async def main():
    # Taktik aus CLI-Argument oder Menü
    if len(sys.argv) >= 3:
        tactic_num, start_pos = int(sys.argv[1]), int(sys.argv[2])
    elif len(sys.argv) == 2:
        tactic_num, start_pos = int(sys.argv[1]), 1
    else:
        tactic_num, start_pos = select_tactic()

    robot = Robot(tactic_num, start_pos)

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT,  lambda: asyncio.create_task(_shutdown(robot, loop)))
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(_shutdown(robot, loop)))

    try:
        robot.wait_for_pullcord()
        await robot.run()
    finally:
        robot.cleanup()


async def _shutdown(robot: Robot, loop: asyncio.AbstractEventLoop):
    robot.log("Shutdown …")
    await robot.stop()
    robot.cleanup()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [t.cancel() for t in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Abgebrochen")
