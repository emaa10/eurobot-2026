from modules.task import Task
from modules.motor_controller import MotorController
from modules.drive_state import DriveState
from modules.lidar import Lidar
from modules.camera import Camera
from modules.pico_com import Pico
from modules.task_presets import TaskPresets

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
        self.motor_controller = MotorController()
        self.lidar = Lidar() if LIDAR else None
        self.camera = Camera() if CAM else None
        
        if LIDAR and not self.lidar.start_scanning():
            self.logger.info("Failed to start Lidar")
            return

        if CAM:
            self.camera.start()
            self.logger.info("Camera started")
                    
        self.task: Task | None = Task(self.motor_controller, self.camera, [['dp200;500;-30']])
        self.tactic: Task | None = Task(self.motor_controller, self.camera, [['dp200;500;-30']])
        self.home_routine: Task | None = Task(self.motor_controller, self.camera, [['dp200;500;-30']])
        
        self.task_presets = TaskPresets()
        
        self.start_positions = {
            # gelb
            1: [25, 25, 0],
            2: [25, 25, 0],
            3: [25, 25, 0],
            # blau
            4: [25, 25, 0],
            5: [25, 25, 0],
            6: [25, 25, 0],
        }
        
        self.home_routines = {
            1: [['hh', 'dd200', 'ta-90', 'hh', 'dd200', 'ta45', 'dd-150', 'sp0;0;0']],
            2: [['hh', 'dd200', 'ta-90', 'hh', 'dd200', 'ta45', 'dd-150', 'sp0;0;0']],
            3: [['hh', 'dd200', 'ta-90', 'hh', 'dd200', 'ta45', 'dd-150', 'sp0;0;0']],
            4: [['hh', 'dd200', 'ta-90', 'hh', 'dd200', 'ta45', 'dd-150', 'sp0;0;0']],
            5: [['hh', 'dd200', 'ta-90', 'hh', 'dd200', 'ta45', 'dd-150', 'sp0;0;0']],
            6: [['hh', 'dd200', 'ta-90', 'hh', 'dd200', 'ta45', 'dd-150', 'sp0;0;0']],
        }
        
        self.tactix = {
            1: [['ta180']],
            2: [['dp200;500;-30']],
            3: [['cd']],
            4: [self.task_presets.flag()],
        }
        
    def set_tactic(self, start_pos: int, tactic: int):
        self.x, self.y, self.theta = self.start_positions[start_pos]
        self.motor_controller.set_pos(self.x, self.y, self.theta)
        self.task_presets.color = 'yellow' if start_pos <= 3 else 'blue'
        
        tactic = self.tactix[tactic]
        home_routine = self.home_routines[start_pos]
        self.tactic = Task(self.motor_controller, self.camera, tactic)
        self.home_routine = Task(self.motor_controller, self.camera, home_routine)
        
    async def home(self):
        self.task = await self.home_routine.next_action()
        
        self.logger.info('Homing routine started')
        
        while True:
            not_done = await self.run()
            if not not_done: break
        
    async def start(self):
        self.task = await self.tactic.next_action()
        
        self.task.time_started = time()
        self.logger.info(f'Tacitc started')
        
    async def run(self) -> bool:        
        state = await self.task.control_loop()
                
        if state.finished: 
            return False
                        
        self.x = state.x
        self.y = state.y
        self.theta = state.theta
        self.task = state.task
        
        # lidar
        if LIDAR:
            latest_scan = self.lidar.get_latest_scan()
            stop = False
            
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
                
            self.motor_controller.stop = False
        
        if LIDAR and not self.lidar.is_running():
            self.logger.info("Lidar thread stopped unexpectedly")
            return False
                
        return True, self.points

async def main():
    try:
        controller = RobotController()
        controller.set_tactic(1, 1)
        await controller.start()
        while True:
            not_done = await controller.run()
            if not not_done:
                break

    finally:
        await controller.motor_controller.set_stop()
        await asyncio.sleep(0.5)
    

if __name__ == '__main__':
    asyncio.run(main())
