from typing import Self

from modules.motor_controller import MotorController
from modules.pathfinding import Pathfinder
from modules.position import Position
from modules.drive_state import  DriveState

import asyncio

class Task():
    def __init__(self, motor_controller: MotorController, actions: list[str] = [], successor: Self | None = None):
        self.motor_controller = motor_controller
        self.initial_actions = actions  # if we abort and want to add task to end
        self.actions = actions
        self.successor = successor
        
        self.pathfinder = Pathfinder()
        
    def add_task(self, task: Self) -> Self:
        if not self.successor:
            self.successor = task
            return

        self.successor.add_task(task)
        
    async def control_loop(self) -> DriveState:
        state = await self.motor_controller.control_loop()
        state.task = self
        
        if state.finished:
            state.task = await self.task.next_action(state.x, state.y)
        
        return state
        
    async def next_action(self, x, y) -> Self:
        if len(self.actions) <= 0:
            if not self.successor: return None
            
            return self.successor.next_action(x, y)
        
        action = self.actions.pop(0)
        prefix = action[0]
        value = action[1:]
        
        match prefix:
            case 'd':
                await self.motor_controller.drive_distance(int(value))
                await asyncio.sleep(0.2)
            case 't':
                await self.motor_controller.turn_angle(float(value))
                await asyncio.sleep(0.2)
            case 'r':
                await self.motor_controller.turn_to(float(value))
                await asyncio.sleep(0.2)
            case 'p':
                target_x, target_y, target_theta = value.split(';')
                points = self.pathfinder.plan(start=Position(x//10, y//10), target=Position(int(target_x)//10, int(target_y)//10))
                actions = []
                for point in points:
                    print(f'{point.x}, {point.y}')
                    actions.extend(self.motor_controller.drive_to(point.x*10, point.y*10))
                actions.append(f'r{target_theta}')
                actions.extend(self.actions)
                self.actions = actions
                print(self.actions)
                return self.next_action(x, y)
                
        return self