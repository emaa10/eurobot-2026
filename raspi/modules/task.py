from typing import Self
from time import time
import logging

from modules.motor_controller import MotorController
from modules.pathfinding import Pathfinder
from modules.position import Position
from modules.drive_state import  DriveState

import asyncio

class Task():
    def __init__(self, motor_controller: MotorController | None, action_set: list[list[str]], successor: Self | None = None, ):
        self.motor_controller = motor_controller
        self.initial_actions = action_set[0]# if we abort and want to add task to end
        self.actions = action_set.pop(0)
        self.current_action = None
        self.successor = successor
        
        self.stopped_since = None
        self.abortable = True
        
        self.logger = logging.getLogger(__name__)
                
        for actions in action_set:
            # self.logger.info(actions)
            self.add_task(Task(self.motor_controller, [actions]))
        
        self.pathfinder = Pathfinder()
        
    def add_task(self, task: Self) -> Self:
        if not self.successor:
            self.successor = task
            return

        self.successor.add_task(task)
        
    async def control_loop(self, time_started) -> DriveState:
        self.logger.info('loop')
        state = await self.motor_controller.control_loop()
        state.task = self
        
        if state.stopped and not self.stopped_since: self.stopped_since = time()
            
        if not state.stopped and self.stopped_since: self.stopped_since = None
            
        if self.stopped_since and self.stopped_since + 5 < time() and self.abortable:
            self.add_task(Task(self.motor_controller, [self.initial_actions]))
            state.task = await self.next_task(state.x, state.y)
        
        if state.finished:
            state.task = await self.next_action(state.x, state.y)
            if state.task: state.finished = False
            
        if time_started + 90 < time():
            pass    # drive home
            
        if time_started + 99 < time():
            self.motor_controller.stop()
            state.finished = True
        
        return state
        
    async def next_action(self, x, y) -> Self:
        if len(self.actions) <= 0:
            if not self.successor: return None
            
            return await self.successor.next_action(x, y)
        
        self.current_action = self.actions.pop(0)
        prefix = self.current_action[:2]
        value = self.current_action[2:]
        
        match prefix:
            case 'dd':
                await self.motor_controller.drive_distance(int(value))
                await asyncio.sleep(0.2)
            case 'dp':
                target_x, target_y, target_theta = value.split(';')
                points = self.pathfinder.proccess(start=Position(x//10, y//10), target=Position(int(target_x)//10, int(target_y)//10))
                actions = []
                for point in points:
                    actions.extend(self.motor_controller.drive_to(point.x*10, point.y*10))
                actions.append(f'r{target_theta}')
                actions.extend(self.actions)
                self.actions = actions
                return self.next_action(x, y)
            case 'ta':
                await self.motor_controller.turn_angle(float(value))
                await asyncio.sleep(0.2)
            case 'tt':
                await self.motor_controller.turn_to(float(value))
                await asyncio.sleep(0.2)
            case 'gl':
                self.abortable = False  # after gripperaction lift not abortable
            case 'gr':
                self.abortable = True  # after gripperaction release abortable again
                
        return self
    
    async def next_task(self, x, y):
        successor = await self.successor.next_action(x, y)
        return successor
    

def main():
    task = Task(None, [['d500', 't50'], ['d340', 't50'], ['d650', 't76']])
    
if __name__ == '__main__':
    main()