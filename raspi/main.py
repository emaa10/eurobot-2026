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

# --- GPIO Pins ---
PIN_PULLCORD    = 22   # Zugschnur (active LOW, pullup)
PIN_TEAM_SELECT = 17   # Team-Schalter: LOW = blau, HIGH = gelb

HOST = '127.0.0.1'
PORT = 5001


class RobotController:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_PULLCORD,    GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PIN_TEAM_SELECT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        logging.basicConfig(
            filename='/home/eurobot/eurobot-2026/raspi/eurobot.log',
            level=logging.INFO,
        )
        self.logger = logging.getLogger(__name__)

        self.color = 'blue' if GPIO.input(PIN_TEAM_SELECT) == GPIO.LOW else 'yellow'
        self.l(f"Team: {self.color}")

        self.points = 0
        self.client_writer: asyncio.StreamWriter | None = None

        # Hardware
        self.esp32   = ESP32()
        self.servos  = Servos()
        self.gripper = Gripper(self.servos)
        self.lidar   = Lidar()
        self.camera  = Camera()

        if not self.lidar.start_scanning():
            self.l("Warning: Lidar konnte nicht gestartet werden")

        self.camera.start()
        self.l("Camera started")

        self.tactic       = Task(self.esp32, self.camera, self.gripper, [[]], self.color)
        self.home_routine = Task(self.esp32, self.camera, self.gripper, [[]], self.color)

        # Startpositionen (Blau) – nur wenn kein 'hm' in der Home-Routine
        self.start_positions = {
            1: [150,  1800, 180],
            2: [600,  1800, 180],
            3: [1050, 1800, 180],
        }

        # Home-Routinen: 'hm' = autonomes Wall-Homing (setzt Position selbst)
        self.home_routines = {
            1: [['hg', 'hm']],
            2: [['hg', 'hm']],
            3: [['hg', 'hm']],
        }

        # Taktiken (Blau-Koordinaten – Task spiegelt für Gelb)
        self.tactics = {
            1: [['dd1000']],   # Test: 1 m geradeaus
            2: [['dd1000']],
            3: [['dd1000']],
            4: [['dd1000']],
        }

        self.start_pos = 1
        self.autonomous_homing = False

    def l(self, msg: str):
        print(msg)
        self.logger.info("MAIN – " + msg)

    # ── Drive helpers (thin wrappers so main.py can call them directly) ────

    async def drive(self, mm: int):
        """Fahre mm Millimeter vorwärts (negativ = rückwärts)."""
        await self.esp32.drive_distance(mm)

    async def turn(self, deg: float):
        """Drehe deg Grad relativ (positiv = im Uhrzeigersinn)."""
        await self.esp32.turn_angle(deg)

    async def turn_to(self, deg: float):
        """Drehe auf absoluten Winkel deg (0–360, Blau-Koordinaten)."""
        await self.esp32.turn_to(deg)

    async def drive_to(self, x: float, y: float):
        """Drehe Richtung (x,y) und fahre hin."""
        await self.esp32.drive_to(x, y)

    async def drive_to_point(self, x: float, y: float, theta: float):
        """Fahre zu (x,y) und richte auf theta aus."""
        await self.esp32.drive_to_point(x, y, theta)

    async def stop(self):
        await self.esp32.set_stop()

    # ── Pullcord ───────────────────────────────────────────────────────────

    def wait_for_pullcord(self):
        self.l("Warte auf Zugschnur …")
        while GPIO.input(PIN_PULLCORD) == GPIO.LOW:
            sleep(0.1)
        self.l("Zugschnur gezogen – Spiel startet")

    # ── TCP Server ─────────────────────────────────────────────────────────

    async def get_command(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        self.l(f"Client verbunden: {addr}")
        self.client_writer = writer
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    self.l(f"Client {addr} getrennt")
                    break
                msg = data.decode().strip()
                self.l(f"Empfangen: {msg}")

                if msg.startswith('st'):   # st{pos};{tactic}
                    start_pos, tactic_num = msg[2:].split(';')
                    self.set_tactic(int(start_pos), int(tactic_num))
                    await self.home()
                    await self.send_message('h')
                    self.wait_for_pullcord()
                    if not self.autonomous_homing:
                        x, y, theta = self.start_positions[self.start_pos]
                        if self.color == 'yellow':
                            x = 3000 - x
                            theta = int((180 - theta) % 360)
                        self.esp32.set_pos(x, y, theta)
                    asyncio.create_task(self.run_tactic())
                    sleep(0.5)

                await self.tactic.perform_action(msg)

        except Exception as e:
            self.l(f"Client-Fehler: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            self.client_writer = None

    async def send_message(self, msg: str) -> bool:
        if not self.client_writer:
            return False
        try:
            self.client_writer.write(msg.encode())
            await self.client_writer.drain()
            return True
        except Exception as e:
            self.l(f"Send-Fehler: {e}")
            return False

    async def start_server(self):
        server = await asyncio.start_server(self.get_command, HOST, PORT)
        self.l(f"Server läuft auf {HOST}:{PORT}")
        async with server:
            await server.serve_forever()

    def set_tactic(self, start_pos_num: int, tactic_num: int):
        self.start_pos = start_pos_num
        tactic         = self.tactics[tactic_num]
        home_routine   = self.home_routines[start_pos_num]
        self.autonomous_homing = any('hm' in step for step in home_routine[0])
        self.l(f"color={self.color}, tactic={tactic_num}, start={start_pos_num}, auto_homing={self.autonomous_homing}")
        self.tactic       = Task(self.esp32, self.camera, self.gripper, tactic,       self.color)
        self.home_routine = Task(self.esp32, self.camera, self.gripper, home_routine, self.color)

    async def home(self):
        self.l("Homing …")
        while True:
            self.home_routine = await self.home_routine.run()
            if not self.home_routine:
                break
        self.l("Homing fertig")
        await self.send_message('h')

    def start_timer(self):
        t = time()
        self.esp32.time_started  = t
        self.servos.time_started = t
        self.l("Timer gestartet")

    async def run(self) -> int:
        if not self.tactic:
            return -1
        self.tactic = await self.tactic.run()
        if not self.tactic:
            self.l("Taktik abgeschlossen")
            return -1
        return self.tactic.points

    async def run_tactic(self):
        self.start_timer()
        while True:
            points = await self.run()
            await self.send_message(f"c{points}")
            if points == -1:
                break
        await self.stop()

    # ── Background tasks ───────────────────────────────────────────────────

    async def camera_loop(self):
        while True:
            tags = self.camera.getTag()
            if tags:
                for tag in tags:
                    self.l(f"Tag {tag.id}: {tag.horizontal_angle:.1f}° {tag.distance:.0f}mm")
            await asyncio.sleep(0.5)

    async def lidar_loop(self):
        while True:
            if not self.lidar.is_running():
                self.l("Warning: Lidar-Thread nicht aktiv")
            await asyncio.sleep(5)

    async def cleanup(self):
        self.logger.info("Cleanup …")
        await self.stop()
        self.lidar.stop()
        GPIO.cleanup()
        self.logger.info("Cleanup fertig")


async def main():
    controller = RobotController()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT,  lambda: asyncio.create_task(shutdown(controller)))
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown(controller)))

    try:
        asyncio.create_task(controller.camera_loop())
        asyncio.create_task(controller.lidar_loop())
        await controller.start_server()
    except Exception as e:
        controller.logger.error(f"Fehler im Main-Loop: {e}")
        await controller.cleanup()


async def shutdown(controller: RobotController):
    controller.logger.info("Shutdown …")
    await controller.cleanup()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.get_running_loop().stop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down")
