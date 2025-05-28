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
            case 'sp':  # set pos
                values = msg[2:].split(';')
                self.motor_controller.set_pos(int(values[0]), int(values[1]), int(values[2]))
            case 'cs': # check stack
                print(self.camera.check_stacks(True)) # debug oder nicht
                # gibt anzahl stacks zurück
            case 'ws': # write servo
                values = msg[2:].split(';')
                self.logger.info(f"set servo cmd: {values}")
                self.gripper.servos.write_servo(int(values[0]), int(values[1]))
            case 'sl':  # stepper lift
                values = msg[2:].split(';')
                self.logger.info(f"set stepper heigth XYZ: {values}")
                self.gripper.stepper.set_pos_mm(int(values[0]), int(values[1]), int(values[2]))
            case 'dd':  # drive distance
                self.logger.info(f"drive distance: {int(msg[2:])}")
                await self.motor_controller.drive_distance(int(msg[2:]))
            case 'dp':  # drive point
                values = msg[2:].split(';')
                print(values)
                print('bassd')
                await self.motor_controller.drive_to_point(int(values[0]), int(values[1]), int(values[2]))
            case 'dh':
                if self.color == 'blue':
                    await self.motor_controller.drive_to_point(2500, 1400, 0)
                else:
                    await self.motor_controller.drive_to_point(500, 1400, 0)
                    
                self.points += 10
            case 'ta':  # turn angle
                self.logger.info(f"turn angle: {int(msg[2:])}")
                await self.motor_controller.turn_angle(int(msg[2:]))
                await self.motor_controller.set_stop()
            case 'tt':  # turn to
                self.logger.info(f"turn to {msg[2:]}")
                await self.motor_controller.turn_to(int(msg[2:]))
            case 'cw':  # clean wheels
                self.logger.info(f"clean wheels")
                await self.motor_controller.clean_wheels()
            case 'ac':  # anfahren cans
                self.logger.info("anfahren cans")
                self.gripper.anfahren()
                sleep(0.5)
            case 'es':  # emergency stop
                self.logger.info("emergency stop!")
                await self.motor_controller.set_stop()
            case 'hg':  # home gripper
                self.logger.info("home gripper")
                self.gripper.home()
            case 'hb':  # home bot
                self.logger.info("home bot")
                await self.motor_controller.home()
            case 'ip':  # increase points
                self.logger.info("increase points")
                increase_points = int(msg[2:])
                self.points += increase_points
            case 'ic': # increase points cam
                self.logger.info("increase points based on cam")
                stacks = self.camera.check_stacks()
                increase_points = 0
                match stacks:
                    case 0: increase_points = 0
                    case 1: increase_points = 4
                    case 2: increase_points = 12
                    case 3: increase_points = 28
                self.points += increase_points
            case 'fd':  # flag down
                self.logger.info("flag down")
                self.gripper.servos.servo_flag(2)
                sleep(0.5)   
            case 'rg':  # release gripper
                self.logger.info("release gripper")
                self.gripper.release()             
            case 'b1':  # build a lvl1 from stack in arena
                self.logger.info("build lvl 1")
                self.gripper.grip_one_layer()
                await self.motor_controller.drive_distance(-300)
                self.gripper.build_one_layer()
            case 'b2':  # build a lvl2 from stack in arena 
                self.logger.info("build lvl 2")
                self.gripper.build_2er()
            case 'gu':  # umgreifen
                self.logger.info("umgreifen")
                self.gripper.release()
                await self.motor_controller.drive_distance(-200)
                self.gripper.grip_unten()
                await self.motor_controller.drive_distance(250)
                self.gripper.servos.grip_außen()
                sleep(1)
                self.gripper.stepper.set_pos_mm(145, 0, 145)
            case 'a2': # add lvl2 onto lvl1
                # ac
                await self.motor_controller.drive_distance(180)
                # b2
                sleep(20)
                # gu
                await self.motor_controller.drive_distance(200)
                # rg
                await self.motor_controller.drive_distance(-200)
                
            case 'xx':
                # sp
                
                # ac
                
                await self.motor_controller.drive_to_point(1900, 700, 0)
                await self.motor_controller.drive_distance(200)
                
                # b2
                
                await self.motor_controller.drive_distance(-250)
                                
                # place 1st stapel
                await self.motor_controller.drive_to_point(1700, 350, 180)
                # rg
                sleep(0.5)
                
                await self.motor_controller.drive_distance(-200)

                # ac

                await self.motor_controller.drive_to_point(2225, 600, 183)
                await self.motor_controller.drive_to_point(2225, 280, 183)

                # b1 
                
                await self.motor_controller.drive_to_point(1700, 550, 180)
                await self.motor_controller.drive_to_point(1700, 320, 180)
                
                # rg
                await self.motor_controller.drive_distance(-200)
                

                # ac
                await self.motor_controller.drive_to_point(1700, 520, 90)
                await self.motor_controller.drive_distance(180)
                # b2 
                
                await self.motor_controller.drive_to_point(1,1,1) # keine Ahnung
                
                # gu
                await self.motor_controller.drive_distance(200)
                # rg
                await self.motor_controller.drive_distance(-200)
            case 'gp': # get pos
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
    