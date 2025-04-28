from modules.task import Task
from modules.motor_controller import MotorController
from modules.drive_state import DriveState
from modules.lidar import Lidar
from modules.camera import Camera

import math
import asyncio
from time import time, sleep
import logging

LIDAR = False
CAM = False

class RobotController:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.theta = 0.0
        
        logging.basicConfig(filename='/home/eurobot/main-bot/raspi/eurobot.log', level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.time_started = time()
        
        self.motor_controller = MotorController()
                        
        self.lidar = Lidar('/dev/ttyUSB0') if LIDAR else None

        self.camera = Camera() if CAM else None
                    
        self.task: Task | None = Task(self.motor_controller, None, [['dp500;200;-30']])
        
        self.start_positions = {
            1: [25, 25, 0],
            2: [25, 25, 0],
            3: [25, 25, 0],
            4: [25, 25, 0],
            5: [25, 25, 0],
            6: [25, 25, 0],
        }
        
        self.tactix = {
            1: [['rt']]
        }
        
    def set_tactic(self, start_pos: int, tactic: int):
        self.x, self.y, self.theta = self.start_positions[start_pos]
        self.motor_controller.set_pos(self.x, self.y, self.theta)
        
        tactic = self.tactix[tactic]
        self.task = Task(self.motor_controller, tactic)
        
    async def control_loop(self, state: DriveState, latest_scan: list[tuple] | None = None):
        # update pos
        self.x = state.x
        self.y = state.y
        self.theta = state.theta
        
        # lidar
        stop = False
            
        if not latest_scan:
            return True if not self.task else False
        
        for angle, distance in latest_scan:
            # point in relation to bot
            d_x = distance * math.sin(angle * math.pi / 180)
            d_y = distance * math.cos(angle * math.pi / 180)
            
            # point in arena
            arena_angle = (-angle) + self.theta
            arena_x = distance * math.cos(arena_angle * math.pi / 180) + self.x
            arena_y = distance * math.sin(arena_angle * math.pi / 180) + self.y
            
            point_in_arena = 50 <= arena_x <= 2950 and 50 <= arena_y <= 1950    # 5cm threshold
            point_in_arena = True
                        
            if (state.direction >= 0 and 0 <= d_y <= 500) and abs(d_x) <= 250 and point_in_arena:
                stop = True
                self.logger.info(f'Obstacle: x: {d_x}, y: {d_y}, angle: {angle}, distance: {distance}')
                break
            
            if  (state.direction <= 0 and 0 >= d_y >= -500) and abs(d_x) <= 250 and point_in_arena:
                stop = True
                self.logger.info(f'Obstacle: x: {d_x}, y: {d_y}, angle: {angle}, distance: {distance}')
                break
                
        self.motor_controller.stop = stop
        
    async def start(self):
        if LIDAR and not self.lidar.start_scanning():
            self.logger.info("Failed to start Lidar")
            return

        if CAM:
            self.camera.start()
            self.logger.info("Camera started")

        
        self.task = await self.task.next_action()
        
        self.time_started = time()
        self.logger.info(f'Started')
        
    async def run(self) -> bool:
        latest_scan = self.lidar.get_latest_scan() if LIDAR else None
        state = await self.task.control_loop(self.time_started)
        
        if state.finished: 
            return False
        
        self.x = state.x
        self.y = state.y
        self.theta = state.theta
        self.task = state.task
        
        
        await self.control_loop(state, latest_scan)
        
        if LIDAR and not self.lidar.is_running():
            self.logger.info("Lidar thread stopped unexpectedly")
            return False
        
        print(self.x)
        
        return True

async def main():
    controller = RobotController()
    await controller.start()
    not_done = True
    while not_done:
        not_done = await controller.run()
    

if __name__ == '__main__':
    asyncio.run(main())
