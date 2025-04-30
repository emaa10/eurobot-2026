from modules.task import Task
from modules.motor_controller import MotorController
from modules.drive_state import DriveState
from modules.lidar import Lidar
from modules.camera import Camera
from modules.pico_com import Pico
from modules.arduino_com import Arduino

import math
import asyncio
from time import time
import logging

LIDAR = False
CAM = True

class RobotController:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.theta = 0.0
        
        self.points = 0
        
        logging.basicConfig(filename='/home/eurobot/main-bot/raspi/eurobot.log', level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.time_started = time()
        
        self.pico_controller = Pico()
                
        self.motor_controller = MotorController()
                        
        self.lidar = Lidar() if LIDAR else None

        self.camera = Camera() if CAM else None
        
        if LIDAR and not self.lidar.start_scanning():
            self.logger.info("Failed to start Lidar")
            return

        if CAM:
            self.camera.start()
            self.logger.info("Camera started")
                    
        self.task: Task | None = Task(self.motor_controller, self.camera, self.pico_controller, [['dp200;500;-30']])
        
        self.start_positions = {
            1: [25, 25, 0],
            2: [25, 25, 0],
            3: [25, 25, 0],
            4: [25, 25, 0],
            5: [25, 25, 0],
            6: [25, 25, 0],
        }
        
        self.tactix = {
            1: [['dd300']],
            2: [['dp200;500;-30']],
            3: [['hh', 'dd200']],
            4: [['cc']],
        }
        
    def set_tactic(self, start_pos: int, tactic: int):
        self.x, self.y, self.theta = self.start_positions[start_pos]
        self.motor_controller.set_pos(self.x, self.y, self.theta)
        
        tactic = self.tactix[tactic]
        self.task = Task(self.motor_controller, self.camera, self.pico_controller, tactic)
        
    async def start(self):
        self.task = await self.task.next_action()
        
        self.time_started = time()
        self.logger.info(f'Started')
        
    async def run(self) -> bool:        
        state = await self.task.control_loop(self.time_started)
                
        if state.finished: 
            return False
                        
        self.x = state.x
        self.y = state.y
        self.theta = state.theta
        self.task = state.task
        
        # lidar
        latest_scan = self.lidar.get_latest_scan() if LIDAR else None
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
            
            point_in_arena = 100 <= arena_x <= 2900 and 100 <= arena_y <= 190    # 5cm threshold
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
        
        if LIDAR and not self.lidar.is_running():
            self.logger.info("Lidar thread stopped unexpectedly")
            return False
                
        return True, self.points

async def main():
    try:
        controller = RobotController()
        controller.set_tactic(1, 3)
        await controller.start()
        
        while True:
            not_done = await controller.run()
            
    finally:
        await controller.motor_controller.set_stop()
        await asyncio.sleep(0.5)
    

if __name__ == '__main__':
    asyncio.run(main())
