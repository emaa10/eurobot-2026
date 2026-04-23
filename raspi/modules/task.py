import asyncio
import logging
from time import time, sleep
from typing import Self

from modules.esp32 import ESP32
from modules.camera import Camera
from modules.gripper import Gripper


def _mirror(x: int, y: int, theta: int | None = None):
    """Spiegelt Koordinaten für das gelbe Team (x-Achse, Mitte = 1500mm)."""
    mx = 3000 - x
    if theta is not None:
        mt = int((180 - theta) % 360)
        return mx, y, mt
    return mx, y


class Task:
    def __init__(self, esp32: ESP32, camera: Camera, gripper: Gripper,
                 action_set: list[list[str]], color: str):
        self.esp32   = esp32
        self.camera  = camera
        self.gripper = gripper
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
        if self.color == 'yellow':
            return _mirror(x, y, theta)
        return (x, y, theta) if theta is not None else (x, y)

    def _angle(self, deg: int) -> int:
        return -deg if self.color == 'yellow' else deg

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    async def perform_action(self, msg: str):
        cmd = msg[:2]

        match cmd:
            case 'dd':  # drive distance mm
                dist = int(msg[2:])
                await self.esp32.drive_distance(dist if self.color == 'blue' else -dist)

            case 'dp':  # drive to point  x;y[;theta]
                vals = msg[2:].split(';')
                x, y = int(vals[0]), int(vals[1])
                theta = int(vals[2]) if len(vals) >= 3 else None
                if theta is not None:
                    px, py, pt = self._pt(x, y, theta)
                    await self.esp32.drive_to(px, py)
                    await self.esp32.turn_to(pt)
                else:
                    px, py = self._pt(x, y)
                    await self.esp32.drive_to(px, py)

            case 'ta':  # turn angle relative degrees
                await self.esp32.turn_angle(self._angle(int(msg[2:])))

            case 'tt':  # turn to absolute degrees
                theta = int(msg[2:])
                if self.color == 'yellow':
                    _, __, theta = _mirror(0, 0, theta)
                await self.esp32.turn_to(theta)

            case 'sp':  # set odometry  x;y;theta
                vals = msg[2:].split(';')
                x, y, t = int(vals[0]), int(vals[1]), int(vals[2])
                if self.color == 'yellow':
                    x, y, t = _mirror(x, y, t)
                self.esp32.set_pos(x, y, t)

            case 'gp':  # print current position
                print(f"pos: {self.esp32.x:.0f}, {self.esp32.y:.0f}, {self.esp32.theta:.1f}")

            case 'es':  # emergency stop
                await self.esp32.set_stop()

            case 'hm':  # autonomous wall homing
                self.logger.info(f"homing ({self.color})")
                back_dist = -300 if self.color == 'blue' else 300
                await self.esp32.drive_distance(back_dist)
                await asyncio.sleep(0.5)
                await self.esp32.drive_distance(-back_dist // 6)
                await self.esp32.turn_angle(90)
                await self.esp32.drive_distance(300)
                await asyncio.sleep(0.5)
                await self.esp32.drive_distance(-50)
                await self.esp32.turn_angle(-90)
                if self.color == 'blue':
                    self.esp32.set_pos(135, 1945, 180)
                else:
                    self.esp32.set_pos(2865, 1945, 0)
                self.logger.info("homing done")

            case 'hg':  # home gripper
                self.gripper.home()

            case 'gr':  # greifer zu
                self.gripper.greifen()

            case 'go':  # greifer auf (open)
                self.gripper.loslassen()

            case 'gi':  # innen greifer zu
                self.gripper.innen_greifen()

            case 'ga':  # außen greifer zu
                self.gripper.aussen_greifen()

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
        if self.esp32.check_time():
            await self.esp32.set_stop()
            return None

        if len(self.actions) <= 0:
            if len(self.action_set) <= 0:
                return None
            self.next_task()

        action = self.actions.pop(0)
        self.logger.info(f"Action: {action}")
        await self.perform_action(action)
        sleep(0.3)

        return self
