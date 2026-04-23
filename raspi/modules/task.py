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

    # ------------------------------------------------------------------
    # Coordinate mirroring
    # ------------------------------------------------------------------

    def _pt(self, x: int, y: int, theta: int | None = None):
        if self.color == 'yellow':
            return _mirror(x, y, theta)
        return (x, y, theta) if theta is not None else (x, y)

    def _angle(self, deg: int) -> int:
        """Spiegelt einen Winkel für gelbes Team."""
        return -deg if self.color == 'yellow' else deg

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    async def perform_action(self, msg: str):
        cmd = msg[:2]
        lidar = getattr(self.esp32, '_lidar', None)  # optional lidar ref

        match cmd:
            case 'dd':  # drive distance
                dist = int(msg[2:])
                self.logger.info(f"drive distance: {dist}")
                await self.esp32.drive_distance(dist if self.color == 'blue' else -dist)

            case 'dp':  # drive to point
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

            case 'ta':  # turn angle (relative)
                deg = self._angle(int(msg[2:]))
                self.logger.info(f"turn angle: {deg}")
                await self.esp32.turn_angle(deg)

            case 'tt':  # turn to (absolute)
                theta = int(msg[2:])
                if self.color == 'yellow':
                    _, __, theta = _mirror(0, 0, theta)
                self.logger.info(f"turn to: {theta}")
                await self.esp32.turn_to(theta)

            case 'sp':  # set position
                vals = msg[2:].split(';')
                x, y, t = int(vals[0]), int(vals[1]), int(vals[2])
                if self.color == 'yellow':
                    x, y, t = _mirror(x, y, t)
                self.esp32.set_pos(x, y, t)

            case 'gp':  # get position (debug)
                self.logger.info(f"pos: {self.esp32.x:.0f}, {self.esp32.y:.0f}, {self.esp32.theta:.1f}")
                print(f"pos: {self.esp32.x:.0f}, {self.esp32.y:.0f}, {self.esp32.theta:.1f}")

            case 'es':  # emergency stop
                self.logger.info("emergency stop")
                await self.esp32.set_stop()

            case 'hb':  # home bot (drive motors)
                self.logger.info("home bot")
                # TODO: implement homing routine for ESP32

            case 'hm':  # autonomous wall homing + position calibration
                self.logger.info(f"autonomous homing ({self.color})")
                # Drehachse: 55mm von hinten, 135mm von links (Zuschauerperspektive)

                # Schritt 1: rückwärts an Hinterwand (y=2000)
                # Blue (theta≈180): drive_distance(-300) → y steigt → trifft y=2000
                # Yellow (theta≈0): drive_distance(+300) → y steigt → trifft y=2000
                back_dist = -300 if self.color == 'blue' else 300
                await self.esp32.drive_distance(back_dist)
                await asyncio.sleep(0.5)

                # Schritt 2: etwas von Hinterwand wegfahren
                await self.esp32.drive_distance(-back_dist // 6)

                # Schritt 3: +90° drehen → blaue Seite zu Linker Wand (x=0),
                #             gelbe Seite zu Rechter Wand (x=3000)
                # Blue:   theta 180→270 (Richtung -x)
                # Yellow: theta   0→90  (Richtung +x)
                await self.esp32.turn_angle(90)

                # Schritt 4: vorwärts in Seitenwand fahren
                await self.esp32.drive_distance(300)
                await asyncio.sleep(0.5)

                # Schritt 5: etwas von Seitenwand wegfahren
                await self.esp32.drive_distance(-50)

                # Schritt 6: -90° zurückdrehen → Roboter schaut wieder aufs Feld
                # Blue:   theta 270→180  Yellow: theta 90→0
                await self.esp32.turn_angle(-90)

                # Schritt 7: kalibrierte Position setzen
                # Drehachse_y = 2000 - 55 = 1945
                # Drehachse_x = 135 (blau) | 2865 (gelb, da 3000-135)
                if self.color == 'blue':
                    self.esp32.set_pos(135, 1945, 180)
                else:
                    self.esp32.set_pos(2865, 1945, 0)
                self.logger.info(f"homing done → pos set")

            case 'hg':  # home gripper
                self.logger.info("home gripper")
                self.gripper.home()

            case 'fd':  # flag down
                self.gripper.servos.servo_flag(2)
                sleep(0.3)

            case 'fu':  # flag up
                self.gripper.servos.servo_flag(1)

            case 'a0':  # anfahren
                self.gripper.anfahren()

            case 'a1':  # anfahren (first time)
                self.gripper.anfahren(True)

            case 'b2':  # build 2er
                self.gripper.build_2er()

            case 'b1':  # build 1er from stack
                self.gripper.grip_one_layer()
                await self.esp32.drive_distance(-300)
                self.gripper.build_one_layer()

            case 'l3':  # lift 3er
                self.gripper.lift_3er()

            case 'rg':  # release gripper
                self.gripper.release()

            case 'gu':  # umgreifen
                self.gripper.release()
                await self.esp32.drive_distance(-200)
                self.gripper.grip_unten()
                await self.esp32.drive_distance(250)
                self.gripper.servos.grip_außen()
                sleep(0.6)
                self.gripper.servos.gripper_in()
                sleep(0.2)
                self.esp32.stepper_set(135, 0, 135)

            case 'ws':  # write servo manually
                vals = msg[2:].split(';')
                self.gripper.servos.write_servo(int(vals[0]), int(vals[1]))

            case 'sl':  # stepper lift
                vals = msg[2:].split(';')
                self.esp32.stepper_set(int(vals[0]), int(vals[1]), int(vals[2]))

            case 'ip':  # increase points (fixed)
                self.points += int(msg[2:])

            case 'ic':  # increase points via camera
                sleep(1)
                stacks = self.camera.check_stacks() if self.camera else 0
                match stacks:
                    case 1: self.points += 4
                    case 2: self.points += 12
                    case 3: self.points += 28

            case 'dh':  # drive home
                if self.color == 'blue':
                    await self.esp32.drive_distance(-200)
                    await self.esp32.turn_to(210)
                    await self.esp32.drive_distance(-1100)
                else:
                    await self.esp32.drive_distance(-200)
                    await self.esp32.turn_to(150)
                    await self.esp32.drive_distance(-1100)

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
