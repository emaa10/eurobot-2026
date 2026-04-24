"""
Serial interface to ESP32 for differential drive (2 stepper motors).

ESP32 Protocol (text, newline-terminated):
  Raspi → ESP32:
    DD{mm}        drive distance in mm (+ forward, - backward)
    TA{deg}       turn by relative angle in degrees
    ST            stop current drive motion immediately
    RS            resume drive motion after stop
    SP{x};{y};{t} set odometry position

  ESP32 → Raspi:
    OK            command completed (DD / TA)
    ERR           error
    P{x};{y};{t}  position update (optional, ESP32 can send periodically)
"""

import serial
import asyncio
import math
import logging


class ESP32:
    # Nach erstem Anschließen: ls /dev/serial/by-id/ → Pfad eintragen
    # CP2102: usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_XXXX-if00
    # CH340:  usb-1a86_USB2.0-Ser_-if00-port0
    PORT = '/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'

    def __init__(self, port: str = PORT, baudrate: int = 115200):
        self.ser = serial.Serial(port, baudrate, timeout=0.05)
        self.logger = logging.getLogger(__name__)

        # Dead-reckoning position (updated after each command)
        self.x: float = 0.0
        self.y: float = 0.0
        self.theta: float = 0.0

    def set_pos(self, x: float, y: float, theta: float):
        self.x, self.y, self.theta = x, y, theta
        self._write(f"SP{x:.0f};{y:.0f};{theta:.1f}")

    def _write(self, cmd: str):
        try:
            self.ser.write(f"{cmd}\n".encode())
        except Exception as e:
            self.logger.error(f"Serial write error: {e}")

    def _read_line(self) -> str | None:
        if self.ser.in_waiting:
            try:
                return self.ser.readline().decode().strip()
            except Exception:
                pass
        return None

    def _parse_position(self, line: str):
        try:
            parts = line[1:].split(';')
            self.x, self.y, self.theta = float(parts[0]), float(parts[1]), float(parts[2])
        except Exception:
            pass

    async def _wait_for_ok(self, direction: int = 0, lidar=None) -> bool:
        """Wartet auf OK/INTERRUPTED vom ESP32. Gibt True zurück wenn OK, False wenn unterbrochen."""
        lidar_stopped = False
        while True:
            line = self._read_line()
            if line == 'OK':
                return True
            if line == 'INTERRUPTED':
                return False
            elif line and line.startswith('P'):
                self._parse_position(line)
            elif line:
                self.logger.info(f"ESP32: {line}")

            if lidar:
                obstacle = lidar.get_stop(self.x, self.y, self.theta, direction)
                if obstacle and not lidar_stopped:
                    self.logger.info(f"Obstacle – stop ({self.x:.0f},{self.y:.0f})")
                    self._write("ST")
                    lidar_stopped = True
                elif not obstacle and lidar_stopped:
                    self.logger.info("Obstacle weg – resume")
                    self._write("RS")
                    lidar_stopped = False

            await asyncio.sleep(0.01)

    async def drive_distance(self, mm: int, lidar=None):
        direction = 1 if mm >= 0 else -1
        self._write(f"DD{mm}")
        ok = await self._wait_for_ok(direction, lidar)
        if ok:
            # Position nur bei vollständiger Fahrt aktualisieren
            rad = math.radians(self.theta)
            self.x += mm * math.sin(rad)
            self.y += mm * math.cos(rad)

    async def turn_angle(self, deg: float, lidar=None):
        self._write(f"TA{int(deg)}")
        ok = await self._wait_for_ok(0, lidar)
        if ok:
            self.theta = (self.theta + deg) % 360

    async def turn_to(self, target: float, lidar=None):
        delta = target - self.theta
        while delta > 180:
            delta -= 360
        while delta < -180:
            delta += 360
        if abs(delta) > 1:
            await self.turn_angle(delta, lidar)

    async def drive_to(self, x: float, y: float, lidar=None):
        dx = x - self.x
        dy = y - self.y
        dist = math.sqrt(dx ** 2 + dy ** 2)
        if dist < 10:
            return
        # Same angle convention as last year
        target_angle = (-math.atan2(dy, dx) * 180 / math.pi + 90) % 360
        await self.turn_to(target_angle, lidar)
        await self.drive_distance(int(dist), lidar)

    async def drive_to_point(self, x: float, y: float, theta: float, lidar=None):
        await self.drive_to(x, y, lidar)
        await self.turn_to(theta, lidar)

    async def home_endstop(self):
        """Rückwärts fahren bis Endstop (GPIO5 am ESP32 LOW), dann OK abwarten."""
        self._write("HE")
        await self._wait_for_ok(0)

    async def set_stop(self):
        self._write("ST")
