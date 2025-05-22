from typing import Self
from time import time
import logging
import asyncio

from modules.motor_controller import MotorController
from modules.camera import Camera
from modules.pathfinding import Pathfinder


class Task():
    def __init__(self, motor_controller: MotorController, camera: Camera, action_set: list[list[str]], color: str):
        self.motor_controller = motor_controller
        self.camera = camera
        
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
        
    async def run(self) -> Self:        
        if self.motor_controller.time_started + 96 < time():
            await self.motor_controller.set_stop()
            return None
        
        if len(self.actions) <= 0:
            if len(self.action_set) <= 0:
                return None
            
            self.next_task()
        
        current_action = self.actions.pop(0)
        prefix = current_action[:2]
        value = current_action[2:]
        
        self.logger.info(f'action: {prefix}, {value}')
        
        match prefix:
            case 'sp':  # set pos
                x, y, theta  = value.split(';')
                self.motor_controller.set_pos(x, y, theta)
            case 'dd':  # drive distance
                await self.motor_controller.drive_distance(int(value))
            case 'dp':  # drive to point
                x, y, theta  = value.split(';')
                await self.motor_controller.drive_to_point(x, y, theta)
            case 'dh':  
                if self.color == 'blue':
                    await self.motor_controller.drive_to_point(2500, 1300, 0)
                else:
                    await self.motor_controller.drive_to_point(500, 1300, 0)
                    
                self.points += 10
            case 'ta':  # turn angle
                await self.motor_controller.turn_angle(float(value))                              
            case 'tt':  # turn to angle
                await self.motor_controller.turn_to(float(value))
            case 'hh':  # home
                await self.motor_controller.home()
            case 'cw':  # clean wheels
                await self.motor_controller.clean_wheels()
                await asyncio.sleep(20)
                await self.motor_controller.set_stop()
            case 'cd':  # check cam
                await asyncio.sleep(1)
                
                angle, distance = self.camera.get_distance()
                print(distance)
                angle, distance = self.camera.get_angle(distance, angle)
                print(distance)
                await self.motor_controller.turn_angle(-90+angle)
                await self.motor_controller.drive_distance(distance)
                await self.motor_controller.turn_angle(90)
            case 'ip':
                self.points += int(value)
                self.logger.info(f'points plus: {value}')
            case 'ts':
                await asyncio.sleep(int(value))

        await asyncio.sleep(0.3)
        
        return self
    