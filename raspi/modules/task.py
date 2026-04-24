import asyncio
import logging
from time import time, sleep
from typing import Self

from modules.esp32 import ESP32
from modules.camera import Camera
from modules.gripper import Gripper
from modules.lidar import Lidar


def _mirror(x: int, y: int, theta: int | None = None):
    """Spiegelt Koordinaten für das gelbe Team (x-Achse, Mitte = 1500mm)."""
    mx = 3000 - x
    if theta is not None:
        mt = int((180 - theta) % 360)
        return mx, y, mt
    return mx, y


class Task:
    def __init__(self, esp32: ESP32, camera: Camera, gripper: Gripper,
                 action_set: list[list[str]], color: str, lidar: Lidar | None = None):
        self.esp32   = esp32
        self.camera  = camera
        self.gripper = gripper
        self.lidar   = lidar
        self.color   = color  # 'blue' | 'yellow'

        self.action_set      = action_set
        self.initial_actions = self.action_set[0]
        self.actions         = self.action_set.pop(0)

        self.points = 0
        self.logger = logging.getLogger(__name__)

    def next_task(self):
        self.initial_actions = self.action_set[0]
        self.actions         = self.action_set.pop(0)

    def _pt(self, x: int, y: int, theta: int | None = None):
        if self.color == 'blue':
            return _mirror(x, y, theta)
        return (x, y, theta) if theta is not None else (x, y)

    def _angle(self, deg: int) -> int:
        return -deg if self.color == 'blue' else deg

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    async def perform_action(self, msg: str):
        cmd = msg[:2]

        match cmd:
            case 'dd':  # drive distance mm
                dist = int(msg[2:])
                await self.esp32.drive_distance(-dist if self.color == 'blue' else dist, self.lidar)

            case 'dp':  # drive to point  x;y[;theta]
                vals = msg[2:].split(';')
                x, y = int(vals[0]), int(vals[1])
                theta = int(vals[2]) if len(vals) >= 3 else None
                if theta is not None:
                    px, py, pt = self._pt(x, y, theta)
                    await self.esp32.drive_to(px, py, self.lidar)
                    await self.esp32.turn_to(pt, self.lidar)
                else:
                    px, py = self._pt(x, y)
                    await self.esp32.drive_to(px, py, self.lidar)

            case 'ta':  # turn angle relative degrees
                await self.esp32.turn_angle(self._angle(int(msg[2:])), self.lidar)

            case 'tt':  # turn to absolute degrees
                theta = int(msg[2:])
                if self.color == 'blue':
                    _, __, theta = _mirror(0, 0, theta)
                await self.esp32.turn_to(theta, self.lidar)

            case 'sp':  # set odometry  x;y;theta
                vals = msg[2:].split(';')
                x, y, t = int(vals[0]), int(vals[1]), int(vals[2])
                if self.color == 'blue':
                    x, y, t = _mirror(x, y, t)
                self.esp32.set_pos(x, y, t)

            case 'gp':  # print current position
                print(f"pos: {self.esp32.x:.0f}, {self.esp32.y:.0f}, {self.esp32.theta:.1f}")

            case 'es':  # emergency stop
                await self.esp32.set_stop()

            case 'hm':  # autonomous wall homing
                self.logger.info(f"homing ({self.color})")
                if self.color == 'blue':
                    # Start facing +x (θ=90): endstop → x=0 wall, forward 32cm, turn left → θ=0, endstop → y=0 wall
                    await self.esp32.home_endstop()
                    await self.esp32.drive_distance(320, self.lidar)
                    await self.esp32.turn_angle(-90, self.lidar)
                    await self.esp32.home_endstop()
                    self.esp32.set_pos(375, 55, 0)
                else:
                    # Start facing -x (θ=270): endstop → x=3000 wall, forward 32cm, turn right → θ=0, endstop → y=0 wall
                    await self.esp32.home_endstop()
                    await self.esp32.drive_distance(320, self.lidar)
                    await self.esp32.turn_angle(90, self.lidar)
                    await self.esp32.home_endstop()
                    self.esp32.set_pos(2625, 55, 0)
                self.gripper.driving()
                self.logger.info("homing done")

            case 'he':  # endstop homing – rückwärts bis Endstop
                await self.esp32.home_endstop()

            case 'hg':  # home gripper
                self.gripper.home()

            case 'co':  # camera open – öffnet die Greifer an den Positionen der eigenen Kistchen
                _GRIPPER_FUNCS = [
                    lambda: self.gripper.servos.grip_links_aussen(1),
                    lambda: self.gripper.servos.grip_links_innen(1),
                    lambda: self.gripper.servos.grip_rechts_innen(1),
                    lambda: self.gripper.servos.grip_rechts_aussen(1),
                ]
                positions = self.camera.get_gripper_positions(self.color) if self.camera else []
                if positions:
                    for p in positions:
                        if 0 <= p < 4:
                            _GRIPPER_FUNCS[p]()
                    self.logger.info(f"camera: Positionen {positions} → Greifer auf")
                else:
                    self.gripper.loslassen()
                    self.logger.info("camera: keine Kistchen sichtbar → alle Greifer auf")

            case 'gr':  # greifer zu
                self.gripper.greifen()

            case 'go':  # greifer auf (open)
                self.gripper.loslassen()

            case 'gi':  # innen greifer zu
                self.gripper.innen_greifen()

            case 'ga':  # außen greifer zu
                self.gripper.aussen_greifen()

            case 'lh':  # lift hoch
                self.gripper.lift_hoch()

            case 'lr':  # lift runter
                self.gripper.lift_runter()

            case 'w1h':  # winker 1 hoch
                self.gripper.winker(1, True)

            case 'w1r':  # winker 1 runter
                self.gripper.winker(1, False)

            case 'w2h':  # winker 2 hoch
                self.gripper.winker(2, True)

            case 'w2r':  # winker 2 runter
                self.gripper.winker(2, False)

            case 'ws':  # write servo manually  id;pos
                vals = msg[2:].split(';')
                self.gripper.servos.write_servo(int(vals[0]), int(vals[1]))

            case 'ip':  # increase points by fixed amount
                self.points += int(msg[2:])

            case 'ic':  # increase points via camera stack detection
                sleep(1)
                stacks = self.camera.check_stacks() if self.camera else 0
                match stacks:
                    case 1: self.points += 4
                    case 2: self.points += 12
                    case 3: self.points += 28

            case _:
                self.logger.info(f"Unknown action: {msg}")

    async def run(self) -> Self | None:
        if len(self.actions) <= 0:
            if len(self.action_set) <= 0:
                return None
            self.next_task()

        action = self.actions.pop(0)
        self.logger.info(f"Action: {action}")
        await self.perform_action(action)
        sleep(0.3)

        return self
