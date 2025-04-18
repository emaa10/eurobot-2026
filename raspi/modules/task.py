from typing import Self

from modules.motor_controller import MotorController
from modules.pathfinding import Pathfinder
from modules.position import Position

import asyncio

class Task():
    def __init__(self, motor_controller: MotorController, actions: list[str] = [], successor: Self | None = None):
        self.motor_controller = motor_controller
        self.actions = actions
        self.successor = successor
        
        self.pathfinder = Pathfinder()
        
    def add_task(self, task: Self) -> Self:
        if not self.successor:
            self.successor = task
            return

        self.successor.add_task(task)
        
    # Sets next action and returns current Task (self or next task if current task finished)
    async def next_action(self, x, y) -> Self:
        if len(self.actions) <= 0:
            if not self.successor: return None
            
            self.successor.next_action()
            return self.successor 
        
        action = self.actions.pop(0)
        prefix = action[0]
        value = action[1:]
        
        match prefix:
            case 'd':
                print("drive")
                await self.motor_controller.drive_distance(int(value))
                await asyncio.sleep(0.2)
            case 't':
                print("Turn")
                await self.motor_controller.turn_angle(float(value))
                await asyncio.sleep(0.2)
                
            # case 'r':
            #     self.motor_controller.turn_to(float(value))
            # case 'p':
            #     target_x, target_y, target_theta = value.split(';')
            #     points = self.pathfinder.plan(start=Position(x//10, y//10), target=Position(int(target_x)//10, int(target_y)//10))
            #     actions = []
            #     for point in points:
            #         print(f'{point.x}, {point.y}')
            #         actions.extend(self.motor_controller.drive_to(point.x*10, point.y*10))
            #     actions.append(f'r{target_theta}')
            #     actions.extend(self.actions)
            #     self.actions = actions
            #     print(self.actions)
            #     return self.next_action(x, y)
                
        return self