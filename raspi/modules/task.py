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
    def __init__(self, motor_controller: MotorController | None, camera: Camera | None, pico_controller: Pico | None, action_set: list[list[str]]):
        self.motor_controller = motor_controller
        self.camera = camera
        self.pico_controller = pico_controller
        self.initial_actions = action_set[0]# if we abort and want to add task to end
        self.actions = action_set.pop(0)
        self.current_action = None
        self.successor = None
        
        self.stopped_since = None
        self.abortable = True
        
        self.logger = logging.getLogger(__name__)
                
        for actions in action_set:
            # self.logger.info(actions)
            self.add_task(Task(self.motor_controller, None, None, [actions]))
        
        self.pathfinder = Pathfinder()
        
        
    def drive_to(self, x: int, y: int) -> list[str]:
        delta_x = x - self.motor_controller.x
        delta_y = y - self.motor_controller.y
                
        dist = math.sqrt(delta_x**2+delta_y**2)
                
        delta_t = (delta_x/dist) - self.motor_controller.theta * math.pi / 180
                
        # normalize theta
        while (delta_t > math.pi): delta_t -= 2 * math.pi
        while (delta_t < -math.pi): delta_t += 2 * math.pi
        
        delta_t *= 180 / math.pi
        
        return [f'ta{delta_t}', f'dd{int(dist)}']

    
    async def drive_to_point(self, value):
        target_x, target_y, target_theta = value.split(';')
        points = self.pathfinder.proccess(start=Position(self.motor_controller.x//10, self.motor_controller.y//10), target=Position(int(target_x)//10, int(target_y)//10))
        actions = []
        for point in points:
            actions.extend(self.drive_to(point.x*10, point.y*10))
        actions.append(f'tt{target_theta}')
        actions.extend(self.actions)
        self.actions = actions
        return await self.next_action()

    async def set_right_stepper(self, pos: int):
        self.pico_controller.set_command("a", pos)

    async def set_mid_stepper(self, pos: int):
        self.pico_controller.set_command("b", pos)

    # 1: up, 2: down
    async def set_left_servo(self, command: int):
        if(command == 1):
            self.pico_controller.set_command("r", 0)
        else:
            self.pico_controller.set_command("r", 180)
                        
    # 1: fully open, 2: grip plate, 3: collision avoidance, 4: closed
    async def set_plate_gripper(self, command: int):
        if(command == 1): self.pico_controller.set_command("s", 180)
        elif(command == 2): self.pico_controller.set_command("s", 120)
        elif(command == 3): self.pico_controller.set_command("s", 130)
        elif(command == 4): self.pico_controller.set_command("s", 0)

    # 1: up, 2: down
    async def set_drive_flag(self, command: int):
        if(command == 1):
            self.pico_controller.set_command("t", 20)
        else:
            self.pico_controller.set_command("t", 165)

    # 1: closed, 2: open
    async def set_grip_right(self, command: int):
        if(command == 1):
            self.pico_controller.set_command("v", 0)
        else:
            self.pico_controller.set_command("v", 60)

    # 1: outwards, 2: inwards, 3: deposit, 4: mid
    async def servo_rotate_right(self, command: int):
        if(command == 1): self.pico_controller.set_command("w", 20)
        elif(command == 2): self.pico_controller.set_command("w", 180)
        elif(command == 3): self.pico_controller.set_command("w", 165)
        elif(command == 4): self.pico_controller.set_command("w", 100)

    async def home_pico(self):
        self.pico_controller.set_command("h", 0)

    async def emergency_stop(self):
        self.pico_controller.set_command("e", 0)



        
    async def control_loop(self, time_started) -> DriveState:
        state = await self.motor_controller.control_loop()
                
        state.task = self
        
        if state.stopped and not self.stopped_since: self.stopped_since = time()
        if not state.stopped and self.stopped_since: self.stopped_since = None
            
        if self.stopped_since and self.stopped_since + 5 < time() and self.abortable:
            self.add_task(Task(self.motor_controller, None, None, [self.initial_actions]))
            state.task = await self.next_task()
        
        if state.finished:
            self.logger.info(f'x: {state.x}, y: {state.y}, theta: {state.theta}')
            
            state.task = await self.next_action()
            if state.task: state.finished = False
            
        if time_started + 90 < time():
            pass    # drive home
            
        if time_started + 9999999 < time():
            self.logger.info('Cutoff')
            await self.motor_controller.set_stop()
            state.finished = True
        
        return state
    
    def add_task(self, task: Self) -> Self:
        if not self.successor:
            self.successor = task
            return

        self.successor.add_task(task)
    
    async def next_task(self):
        return await self.successor.next_action()
        
    async def next_action(self) -> Self:
        if len(self.actions) <= 0:
            if not self.successor: return None
            
            return await self.successor.next_action()
        
        self.current_action = self.actions.pop(0)
        prefix = self.current_action[:2]
        value = self.current_action[2:]
        
        
        match prefix:
            case 'dd':
                await self.motor_controller.drive_distance(int(value))
            case 'dp':
                return self.drive_to_point(value)
            case 'ta':
                await self.motor_controller.turn_angle(float(value))
            case 'tt':
                await self.motor_controller.turn_to(float(value))
            case 'hh':
                await self.motor_controller.home()
                return await self.next_action()
            case 'cc':
                if not self.camera.check_cans():
                    await asyncio.sleep(0.5)
                    if not self.camera.check_cans():
                        self.logger.info("skip")
                        return await self.next_task()
                    
                await asyncio.sleep(1)
                
                angle, distance = self.camera.get_distance()
                angle_cans = self.camera.get_angle()
                print(f"dist: {distance} - angle {angle} - angle cans {angle_cans}")
                
                # self.logger.info(angle_cans)
                
                # dist = math.sqrt(distance**2-40**2)
                
                actions = [f'ta{angle}'].extend(self.actions)
                self.actions = actions
                # actions = [f'ta{angle_cans}', f'dd{dist}', f'ta{90}']
                
                
                
                # actions = [f'dd{distance}'].extend(self.actions)
                # self.actions = actions


        await asyncio.sleep(0.3)
        
        return self
    
