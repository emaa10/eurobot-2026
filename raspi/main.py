"""
Eurobot 2026 – Hauptprogramm

Startet via start.sh (team-Auswahl interaktiv) oder systemd (--team blue/yellow).
Alle Steuerung (Taktik, Homing, Test-Befehle) läuft über die TCP-Verbindung.
"""

import argparse
import asyncio
import logging
import signal
import copy
import RPi.GPIO as GPIO
from enum import Enum
from time import time

from modules.task import Task
from modules.camera import Camera
from modules.esp32 import ESP32
from modules.servos import Servos
from modules.gripper import Gripper
from modules.lidar import Lidar

PIN_PULLCORD = 22   # Pull-Up: LOW = Schnur drin, HIGH-Flanke = Start

HOST     = '127.0.0.1'
PORT     = 5001
LOG_FILE = '/home/eurobot/eurobot-2026/raspi/eurobot.log'

# Taktiken in Blau-Koordinaten – Task spiegelt für Gelb.
# Homing (hg + hm) wird von 'ready' automatisch davor ausgeführt.
TACTICS = {
    1: [['hg', 'lh', 'dd100', 'ta-15', 'dd800', 'ta10', 'dd680', 'ta90', 'dd350', 'ta70', 'dd1700', 'ta90']],
    2: [['dd100', 'ta-10', 'dd800', 'ta100', 'go', 'dd700', 'dd-100', 'ta70', 'dd1000', 'dd-70', 'ta90']],
    3: [['hg', 'lh', 'dd100', 'ta-15', 'dd800', 'ta10', 'dd680', 'ta90', 'dd350', 'ta70', 'dd1700', 'ta90']], # 1 mit cursor
    4: [['hg', 'dd1000', 'ta90', 'dd300', 'ta-90', 'dd800', 'dd-300', 'ta-90', 'dd800', 'dd-300',
         'ta-90', 'dd2000', 'dd-300', 'ta180', 'dd2000', 'dd-300', 'ta-90', 'dd1200',
         'w2r', 'dd-700', 'w2h', 'ta90', 'dd1000', 'ta90', 'dd500', 'ta-90', 'dd800']],
    5: [['hg', 'dd1000', 'ta90', 'dd800', 'ta-90', 'dd500', 'co', 'dd200', 'cg', 'dd-500',
         'ta90', 'dd300', 'go', 'dd-300', 'ta180', 'dd1000', 'ta-90', 'dd1000']],
}


class State(Enum):
    IDLE    = 'idle'
    HOMING  = 'homing'
    READY   = 'ready'     # Homing fertig, wartet auf Zugschnur
    RUNNING = 'running'
    DONE    = 'done'


# ── Log-Handler: schreibt Log-Zeilen in eine asyncio.Queue ────────────────
class _QueueLogHandler(logging.Handler):
    def __init__(self, queue: asyncio.Queue):
        super().__init__()
        self.queue = queue
        self.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                                            datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            self.queue.put_nowait(self.format(record))
        except Exception:
            pass


# ── Haupt-Controller ──────────────────────────────────────────────────────
class Robot:
    def __init__(self, team: str):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_PULLCORD, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        logging.basicConfig(
            filename=LOG_FILE, level=logging.INFO,
            format='%(asctime)s %(levelname)s %(message)s',
        )
        self.logger = logging.getLogger('eurobot')

        # Log-Queue: Hintergrund-Task streamt Einträge zum Client
        self._log_queue: asyncio.Queue = asyncio.Queue()
        self.logger.addHandler(_QueueLogHandler(self._log_queue))

        # Zustand
        self.state      = State.IDLE
        self.team       = team
        self.tactic_num = 1
        self._game_task: asyncio.Task | None = None
        self._writer:    asyncio.StreamWriter | None = None

        # Hardware
        self.esp32   = ESP32()
        self.servos  = Servos()
        self.gripper = Gripper(self.servos)
        self.lidar   = Lidar()
        self.camera  = Camera()

        if not self.lidar.start_scanning():
            self.log("Warning: Lidar nicht gestartet")
        self.camera.start()

        self.log(f"Bereit. Team: {self.team}")

    # ── Logging ───────────────────────────────────────────────────────────

    def log(self, msg: str):
        print(msg)
        self.logger.info(msg)

    # ── Senden an Client ──────────────────────────────────────────────────

    async def _send(self, line: str):
        if self._writer and not self._writer.is_closing():
            try:
                self._writer.write((line.rstrip() + '\n').encode())
                await self._writer.drain()
            except Exception:
                pass

    async def _ok(self, msg: str = ''):
        await self._send(f"OK  {msg}".rstrip())

    async def _err(self, msg: str):
        await self._send(f"ERR {msg}")

    async def _status(self):
        lines = [
            f"state    {self.state.value}",
            f"team     {self.team}",
            f"tactic   {self.tactic_num}",
            f"pos      x={self.esp32.x:.0f} y={self.esp32.y:.0f} θ={self.esp32.theta:.1f}°",
            f"lidar    {'ok' if self.lidar.is_running() else 'FEHLT'}",
            f"pullcord {'gezogen' if GPIO.input(PIN_PULLCORD) == GPIO.HIGH else 'drin'}",
        ]
        await self._send("─── Status " + "─" * 30)
        for l in lines:
            await self._send("  " + l)
        await self._send("─" * 41)

    # ── Befehls-Dispatcher ────────────────────────────────────────────────

    async def handle_cmd(self, raw: str):
        parts = raw.strip().split()
        if not parts:
            return
        cmd, args = parts[0].lower(), parts[1:]

        match cmd:

            case 'status' | 's':
                await self._status()

            case 'team':
                if not args or args[0] not in ('blue', 'yellow', 'blau', 'gelb'):
                    await self._err("Verwendung: team blue|yellow")
                    return
                self.team = 'blue' if args[0] in ('blue', 'blau') else 'yellow'
                self.log(f"Team: {self.team}")
                await self._ok(f"team={self.team}")

            case 'tactic' | 't':
                if not args or not args[0].isdigit():
                    await self._err(f"Verwendung: tactic <n>  (verfügbar: {list(TACTICS)})")
                    return
                n = int(args[0])
                if n not in TACTICS:
                    await self._err(f"Taktik {n} nicht vorhanden. Verfügbar: {list(TACTICS)}")
                    return
                self.tactic_num = n
                self.log(f"Taktik: {self.tactic_num}")
                await self._ok(f"tactic={self.tactic_num}")

            case 'ready' | 'r':
                if self.state not in (State.IDLE, State.DONE):
                    await self._err(f"Nur im IDLE/DONE möglich (aktuell: {self.state.value})")
                    return
                self._game_task = asyncio.create_task(self._flow_ready())

            case 'home' | 'h':
                if self.state not in (State.IDLE, State.DONE):
                    await self._err(f"Nur im IDLE/DONE möglich (aktuell: {self.state.value})")
                    return
                asyncio.create_task(self._flow_home_only())

            case 'stop':
                await self.esp32.set_stop()
                if self._game_task and not self._game_task.done():
                    self._game_task.cancel()
                self.state = State.IDLE
                await self._ok("gestoppt – zurück auf IDLE")

            case 'drive' | 'd':
                if not args:
                    await self._err("Verwendung: drive <mm>")
                    return
                asyncio.create_task(self._test_drive(int(args[0])))

            case 'turn':
                if not args:
                    await self._err("Verwendung: turn <deg>")
                    return
                asyncio.create_task(self._test_turn(float(args[0])))

            case 'servo':
                if len(args) < 2:
                    await self._err("Verwendung: servo <id> <pos>")
                    return
                self.servos.write_servo(int(args[0]), int(args[1]))
                await self._ok(f"servo {args[0]} → {args[1]}")

            case 'gripper' | 'g':
                sub = args[0].lower() if args else ''
                match sub:
                    case 'open'  | 'o': self.gripper.loslassen()
                    case 'close' | 'c': self.gripper.greifen()
                    case 'home'  | 'h': self.gripper.home()
                    case _:
                        await self._err("Verwendung: gripper open|close|home")
                        return
                await self._ok(f"gripper {sub}")

            case 'help' | '?':
                await self._help()

            case _:
                await self._err(f"Unbekannt: '{cmd}'  –  'help' für Übersicht")

    async def _help(self):
        lines = [
            "─── Befehle " + "─" * 29,
            "  status / s              aktuellen Zustand anzeigen",
            "  team blue|yellow        Team setzen",
            "  tactic <n> / t <n>      Taktik wählen",
            "  ready / r               Homing + Zugschnur + Taktik starten",
            "  home / h                nur Homing (kein Spielstart)",
            "  stop                    Notfall-Stopp",
            "  drive <mm> / d <mm>     Test: fahre mm",
            "  turn <deg>              Test: drehe deg°",
            "  servo <id> <pos>        Test: Servo direkt setzen",
            "  gripper open|close|home / g o|c|h",
            "─" * 41,
        ]
        for l in lines:
            await self._send(l)

    # ── Spielablauf ───────────────────────────────────────────────────────

    async def _flow_home_only(self):
        self.state = State.HOMING
        self.log("Homing gestartet …")
        await self._do_homing()
        self.state = State.IDLE
        self.log("Homing fertig")
        await self._ok("Homing fertig – zurück auf IDLE")

    async def _flow_ready(self):
        # 1. Homing
        self.state = State.HOMING
        self.log(f"Homing gestartet (team={self.team} tactic={self.tactic_num})")
        await self._do_homing()

        # 2. Warten auf Zugschnur
        self.state = State.READY
        self.log("Homing fertig – warte auf Zugschnur …")
        while GPIO.input(PIN_PULLCORD) == GPIO.LOW:
            await asyncio.sleep(0.05)

        # 3. Taktik ausführen
        self.log("Zugschnur – Spiel startet!")
        self.state = State.RUNNING
        await self._run_tactic()
        self.state = State.DONE
        self.log("Spiel fertig")

    async def _do_homing(self):
        self.log("Servos werden aktiviert …")
        self.servos.attach_all()
        homing = Task(self.esp32, self.camera, self.gripper,
                      [['hg', 'hm']], self.team, self.lidar)
        while True:
            homing = await homing.run()
            if not homing:
                break

    async def _run_tactic(self):
        actions = copy.deepcopy(TACTICS[self.tactic_num])
        task    = Task(self.esp32, self.camera, self.gripper, actions, self.team, self.lidar)

        timer = asyncio.create_task(self._game_timer())
        try:
            while True:
                task = await task.run()
                if not task:
                    break
        finally:
            timer.cancel()
            await self.esp32.set_stop()
            self.servos.alle_auf()

    async def _game_timer(self):
        """Zentrales Zeitlimit: stoppt nach 99s alles vom Raspi aus."""
        GAME_TIME = 98
        await asyncio.sleep(GAME_TIME)
        self.log(f"Spielzeit ({GAME_TIME}s) abgelaufen – stoppe.")
        await self.esp32.set_stop()
        self.servos.alle_auf()
        if self._game_task and not self._game_task.done():
            self._game_task.cancel()
        self.state = State.DONE

    async def _test_drive(self, mm: int):
        await self.esp32.drive_distance(mm, self.lidar)
        await self._ok(f"drive {mm} mm fertig")

    async def _test_turn(self, deg: float):
        await self.esp32.turn_angle(deg, self.lidar)
        await self._ok(f"turn {deg}° fertig")

    # ── TCP-Server ────────────────────────────────────────────────────────

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')

        # Vorherige Verbindung schließen wenn noch offen
        if self._writer and not self._writer.is_closing():
            self._writer.close()
        self._writer = writer

        self.log(f"Client verbunden: {addr}")
        await self._send("── Eurobot 2026 ── verbunden. 'help' für Befehle, 'status' für Zustand.")
        await self._status()

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                await self.handle_cmd(data.decode())
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        except Exception as e:
            self.log(f"Client-Fehler: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            if self._writer is writer:
                self._writer = None
            self.log(f"Client getrennt: {addr}")

    async def _log_stream_loop(self):
        """Schickt neue Log-Einträge aus der Queue zum Client."""
        while True:
            msg = await self._log_queue.get()
            await self._send(f"LOG {msg}")

    async def start(self):
        server = await asyncio.start_server(self.handle_client, HOST, PORT)
        self.log(f"Server bereit auf {HOST}:{PORT}")
        asyncio.create_task(self._log_stream_loop())
        asyncio.create_task(self._camera_loop())
        asyncio.create_task(self._lidar_loop())
        async with server:
            await server.serve_forever()

    # ── Hintergrund-Tasks ─────────────────────────────────────────────────

    async def _camera_loop(self):
        _had_tags = False
        TAG_NAMEN = {Camera.TAG_BLUE: 'blau', Camera.TAG_YELLOW: 'gelb'}
        GREIFER   = ['links-außen', 'links-innen', 'rechts-innen', 'rechts-außen']
        while True:
            tags = self.camera.getTag()
            if tags:
                _had_tags = True
                parts = [
                    f"{TAG_NAMEN.get(t.id, f'ID {t.id}')} ({t.horizontal_angle:+.1f}°, {t.distance:.0f}mm)"
                    for t in sorted(tags, key=lambda t: t.horizontal_angle)
                ]
                positions = self.camera.get_gripper_positions(self.team)
                if positions:
                    gr = ', '.join(GREIFER[p] for p in positions if 0 <= p < 4)
                    self.log(f"[CAM] {' | '.join(parts)} → Greifer auf: {gr}")
                else:
                    self.log(f"[CAM] {' | '.join(parts)} → keine eigenen Kistchen")
            elif _had_tags:
                _had_tags = False
                self.log("[CAM] keine Tags sichtbar")
            await asyncio.sleep(0.5)

    async def _lidar_loop(self):
        while True:
            if not self.lidar.is_running():
                self.log("Warning: Lidar-Thread nicht aktiv")
            await asyncio.sleep(5)

    def cleanup(self):
        self.lidar.stop()
        GPIO.cleanup()


# ── Entry point ───────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Eurobot 2026 Hauptprogramm')
    p.add_argument('--team', choices=['blue', 'yellow'], default='blue',
                   help='Teamfarbe (default: blue)')
    return p.parse_args()


async def main():
    args  = _parse_args()
    robot = Robot(team=args.team)
    loop  = asyncio.get_running_loop()

    loop.add_signal_handler(signal.SIGINT,  lambda: asyncio.create_task(_shutdown(robot, loop)))
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(_shutdown(robot, loop)))

    await robot.start()


async def _shutdown(robot: Robot, loop: asyncio.AbstractEventLoop):
    robot.log("Shutdown …")
    await robot.esp32.set_stop()
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
