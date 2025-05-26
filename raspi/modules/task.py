from typing import Self
from time import time, sleep
import logging
import asyncio

from modules.motor_controller import MotorController
from modules.camera import Camera
from modules.pathfinding import Pathfinder
from modules.gripper import Gripper


class Task():
    def __init__(self, motor_controller: MotorController, camera: Camera, gripper: Gripper, action_set: list[list[str]], color: str):
        self.motor_controller = motor_controller
        self.camera = camera
        self.gripper = gripper
        
        self.action_set = action_set
        self.initial_actions = self.action_set[0] # if we abort and want to add task to end
        self.actions = self.action_set.pop(0)
        
        self.color = color
                        
        self.points = 0
        
        self.logger = logging.getLogger(__name__)        
        
        self.pathfinder = Pathfinder()
    
    def next_task(self):
        self.initial_actions = self.action_set[0]
        self.actions = self.action_set.pop(0)
        
    async def perform_action(self, msg):
        cmd = msg[:2]
        match cmd:
            case 'sp':
                values = msg[2:].split(';')
                self.motor_controller.set_pos(int(values[0]), int(values[1]), int(values[2]))
            case 'cs': #check stack
                print(self.camera.check_stacks(True)) # debug oder nicht
                # gibt anzahl stacks zurück
            case 'ws': # write servo
                values = msg[2:].split(';')
                self.logger.info(f"set servo cmd: {values}")
                self.gripper.servos.write_servo(int(values[0]), int(values[1]))
            case 'ra':
                self.gripper.release()
            case 'sl': # stepper lift
                values = msg[2:].split(';')
                self.logger.info(f"set stepper heigth XYZ: {values}")
                self.gripper.stepper.set_pos_mm(int(values[0]), int(values[1]), int(values[2]))
            case 'dd': # drive distance
                self.logger.info(f"drive distance: {int(msg[2:])}")
                await self.motor_controller.drive_distance(int(msg[2:]))
            case 'dp':
                values = msg[2:].split(';')
                print(values)
                print('bassd')
                await self.motor_controller.drive_to_point(int(values[0]), int(values[1]), int(values[2]))
            case 'ta': # turn angle
                self.logger.info(f"turn angle: {int(msg[2:])}")
                await self.motor_controller.turn_angle(int(msg[2:]))
                await self.motor_controller.set_stop()
            case 'tt': # turn to
                self.logger.info(f"turn to {msg[2:]}")
                await self.motor_controller.turn_to(int(msg[2:]))
            case 'cw': # clean wheels
                self.logger.info(f"clean wheels")
                await self.motor_controller.clean_wheels()
            case 'ac': # anfahren cans
                self.logger.info("anfahren cans")
                self.gripper.anfahren()
            case 'gc': # grip cans
                self.logger.info("grip cans")
                self.stepper.down()
                sleep(1)
                self.servos.grip_cans()
                sleep(0.5)
                self.stepper.lift()
                sleep(1)
                self.servos.gripper_in()
                sleep(0.5)
                self.gripper.servos.servo_mitte_lift(2)
            case 'es': # emergency stop
                await self.motor_controller.set_stop()
                self.logger.info("emergency stop!")
            case 'hg': # home gripper
                self.gripper.home()
                self.logger.info("home gripper")
            case 'hb': # home bot
                await self.motor_controller.home()
                self.logger.info("homed bot")
            case 'ip':
                increase_points = int(msg[2:])
                self.points += increase_points
            case 'fd':
                self.gripper.servos.servo_flag(2)
            case 'll': #test gripper lift strength
                self.gripper.servos.servo_plate_rotate(1)
                sleep(0.1)
                self.gripper.stepper.set_pos_mm(5, 0, 5)
                sleep(0.1)
                self.gripper.servos.servo_left_rotate(3)
                self.gripper.servos.servo_right_rotate(3)
                sleep(1)
                await self.motor_controller.drive_distance(150)

                self.gripper.servos.servo_left_grip(2)
                self.gripper.servos.servo_right_grip(2)
                sleep(1)
                self.gripper.stepper.set_pos_mm(145, 0, 145)
                sleep(1)
                await self.motor_controller.drive_distance(150)
                self.gripper.release()
                await self.motor_controller.drive_distance(-300)
                
            case 's1': # seperate 1er
                self.gripper.anfahren()
                sleep(0.3)
                await self.motor_controller.drive_distance(350)
                self.gripper.grip_one_layer()
                await self.motor_controller.drive_distance(-300)
                self.gripper.build_one_layer()
            case 'a2': # add 2er --> aktueller wo wir dran sind
                self.gripper.anfahren()
                sleep(0.5)
                await self.motor_controller.drive_distance(180)
                self.gripper.seperate()
                sleep(20)
                self.gripper.release()
                await self.motor_controller.drive_distance(-200)
                self.gripper.grip_unten()
                await self.motor_controller.drive_distance(250)
                self.gripper.servos.servo_left_grip(2)
                self.gripper.servos.servo_right_grip(2)
                sleep(1)
                self.gripper.stepper.set_pos_mm(145, 0, 145)
                await self.motor_controller.drive_distance(200)
                self.gripper.release()
                await self.motor_controller.drive_distance(-200)
                
            case 'xx': # gerade nur ersten anfahren und zerlegen
                self.motor_controller.set_pos(1700, 215, 0)
                
                self.gripper.anfahren()
                
                # await self.motor_controller.drive_to_point(1900, 700, 0)
                # await self.motor_controller.drive_distance(200)
                await self.motor_controller.drive_distance(250) # entfernen (war nur zum testen)
                
                self.gripper.seperate()
                
                await self.motor_controller.drive_distance(-250)
                                
                # # place 1st stapel
                # await self.motor_controller.drive_to_point(1700, 350, 180)
                # self.gripper.release()
                # sleep(0.5)
                
                # await self.motor_controller.drive_distance(-200)

                # self.gripper.anfahren()

                # await self.motor_controller.drive_to_point(2225, 600, 183)
                # await self.motor_controller.drive_to_point(2225, 280, 183)

                # # grip 2nd level
                # self.gripper.grip_one_layer()
                
                # await self.motor_controller.drive_distance(-300)
                
                # # build level
                # self.gripper.build_one_layer()
                
                # await self.motor_controller.drive_to_point(1700, 550, 180)
                # await self.motor_controller.drive_to_point(1700, 320, 180)
                
                # # place on top of level 2
                # self.servos.release_all()
                # sleep(1)
                # #await self.motor_controller.drive_distance(-200)
                # await self.motor_controller.drive_to_point(1700, 520, 90)

                # await self.motor_controller.drive_to_point(2575, 400, 90)
                # # await self.motor_controller.drive_to_point(2600, 400, 90)
                # await self.motor_controller.drive_to_point(2710, 400, 90)
                
                # self.stepper.down()
                # sleep(1)
                # self.servos.grip_cans()
                # sleep(1)
                # self.stepper.lift()
                # sleep(1)
                # self.servos.gripper_in()
                # sleep(1)
                # self.servos.release_all()
                # sleep(1)
                
                # await self.motor_controller.drive_to_point(2510, 400, 90)
                
                # self.servos.pos_anfahren()
                # self.stepper.down()
                # sleep(0.5)
                # self.servos.servo_plate_rotate(1)
                # self.servos.gripper_in()
                
                # await self.motor_controller.drive_to_point(2710, 400, 90)
                # self.servos.grip_unten()
                # self.stepper.set_pos_mm(20, 0, 20)
            case 'gp':
                x, y, theta = self.motor_controller.encoder.get_pos()
                print(f'{x}, {y}, {theta}')
            case _: # default
                self.logger.info(f"Unknown msg: {msg}")
                
    async def run(self) -> Self:        
        if self.motor_controller.time_started + 96 < time():
            await self.motor_controller.set_stop()
            return None
        
        if len(self.actions) <= 0:
            if len(self.action_set) <= 0:
                return None
            
            self.next_task()
        
        current_action = self.actions.pop(0)
        
        await self.perform_action(current_action)
        sleep(0.3)
        
        return self
    