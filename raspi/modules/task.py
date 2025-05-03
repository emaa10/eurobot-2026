import math
from typing import Self
from time import time
import logging

from modules.motor_controller import MotorController
from modules.camera import Camera
from modules.pathfinding import Pathfinder
from modules.position import Position
from modules.drive_state import DriveState
from modules.pico_com import Pico

import asyncio

class Task():
    def __init__(self, motor_controller: MotorController, camera: Camera, pico_controller: Pico, action_set: list[list[str]], color: str):
        self.motor_controller = motor_controller
        self.camera = camera
        self.pico_controller = pico_controller
        self.initial_actions = action_set[0]# if we abort and want to add task to end
        self.actions = action_set.pop(0)
        self.current_action = None
        self.successor = None
        self.color = color
                        
        self.points = 1
        
        self.logger = logging.getLogger(__name__)        
                
        for actions in action_set:
            self.add_task(Task(self.motor_controller, self.camera, self.motor_controller, [actions], self.color))
        
        self.pathfinder = Pathfinder()
    
    def add_task(self, task: Self) -> Self:
        if not self.successor:
            self.successor = task
            return

        self.successor.add_task(task)
    
    async def next_task(self):
        return await self.successor.run()
        
    async def run(self) -> Self:        
        if self.motor_controller.time_started + 80 < time() and not self.home:
            await self.motor_controller.drive_home(self.color)
            self.points += 9
            self.actions = []
            self.successor = None
            return self
        
        if self.motor_controller.time_started + 97 < time():
            await self.motor_controller.set_stop()
            self.pico_controller.emergency_stop()
            return None
        
        if len(self.actions) <= 0:
            if not self.successor:
                return None
            
            self.successor.points = self.points
            return await self.successor.run()
        
        self.current_action = self.actions.pop(0)
        prefix = self.current_action[:2]
        value = self.current_action[2:]
        
        self.logger.info(prefix)
        
        match prefix:
            case 'sp':  # set pos
                x, y, theta  = value.split(';')
                self.motor_controller.set_pos(x, y, theta)
            case 'dd':  # drive distance
                await self.motor_controller.drive_distance(int(value))
            case 'dp':  # drive to point
                x, y, theta  = value.split(';')
                await self.motor_controller.drive_to_point(x, y, theta)
                print(self.motor_controller.x)
                print(self.motor_controller.y)
                print(self.motor_controller.theta)
            case 'dh':
                if self.color == 'blue':
                    await self.motor_controller.drive_to_point(2500, 1100, 0)
                else:
                    await self.motor_controller.drive_to_point(500, 1100, 0)
                
                while self.motor_controller.time_started + 90 > time():
                    await asyncio.sleep(1)
                
                if self.color == 'blue':
                    await self.motor_controller.drive_to_point(2500, 1400, 0)
                else:
                    await self.motor_controller.drive_to_point(500, 1400, 0)
                    
                self.points += 9
            case 'ta':  # turn angle
                await self.motor_controller.turn_angle(float(value))                              
                # return await self.next_action()
            case 'tt':  # turn to angle
                await self.motor_controller.turn_to(float(value))
            case 'fd':  # flag down
                self.pico_controller.set_drive_flag(2)
                self.points += 20
            case 'fu':  # flag up
                self.pico_controller.set_drive_flag(1)
            case 'gs':  # get stapel
                self.motor_controller.abortable = False
                pass
            case 'rs':  # release stapel
                self.motor_controller.abortable = True
                pass
            case 'hh':  # home
                await self.motor_controller.home()
            case 'cw':  # clean wheels
                await self.motor_controller.clean_wheels()
                await asyncio.sleep(20)
                await self.motor_controller.set_stop()
            case 'cd':  # check cam
                await asyncio.sleep(1)
                print("1")
                
                angle, distance = self.camera.get_distance()
                print(distance)
                angle, distance = self.camera.get_angle(distance, angle)
                print(distance)
                await self.motor_controller.turn_angle(-90+angle)
                await self.motor_controller.drive_distance(distance)
                await self.motor_controller.turn_angle(90)



        await asyncio.sleep(0.3)
        
        return self
    
