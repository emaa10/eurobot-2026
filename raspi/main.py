from modules.task import Task
from modules.camera import Camera
from modules.task_presets import TaskPresets
from modules.motor_controller import MotorController
from modules.pico_com import Pico

import math
import asyncio
from time import time
import logging


class RobotController:
    def __init__(self):
        CAM = False
        
        self.start_pos = 0
        self.points = 0
        
        logging.basicConfig(filename='/home/eurobot/main-bot/raspi/eurobot.log', level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.time_started = time()
        
        self.motor_controller = MotorController()
        self.camera = Camera() if CAM else None
        self.pico_controller = Pico()

        if CAM:
            self.camera.start()
            self.logger.info("Camera started")
                    
        self.tactic: Task | None = None
        self.home_routine: Task | None = None
        
        self.task_presets = TaskPresets()
        
        self.start_positions = {
            # gelb
            1: [200, 950, 90],
            2: [25, 25, 0],
            3: [25, 25, 0],
            # blau
            4: [25, 25, 0],
            5: [25, 25, 0],
            6: [25, 25, 0],
        }
        
        self.home_routines = {
            1: [['hh', 'dd50', 'ta-90', 'hh', 'dd100']],
            2: [['hh', 'dd200', 'ta-90', 'hh', 'dd200', 'ta45', 'dd-150', 'sp0;0;0']],
            3: [['hh', 'dd50', 'ta90', 'hh', 'dd100']],
            4: [['hh', 'dd50', 'ta-90', 'hh', 'dd100']],
            5: [['hh', 'dd200', 'ta-90', 'hh', 'dd200', 'ta45', 'dd-150', 'sp0;0;0']],
            6: [['hh', 'dd50', 'ta90', 'hh', 'dd100']],

        }
        
        self.tactix = {
            1: [['dd180']],
            2: [['dd500']],
            3: [['cd']],
            4: [self.task_presets.flag()],
        }
        
    def set_tactic(self, start_pos_num: int, tactic_num: int):
        color = 'yellow' if start_pos_num <= 3 else 'blue'
        self.start_pos = start_pos_num
        self.task_presets.color = color
        
        tactic = self.tactix[tactic_num]
        home_routine = self.home_routines[start_pos_num]
                
        self.tactic = Task(self.motor_controller, self.camera, self.pico_controller, tactic, color)
        self.home_routine = Task(self.motor_controller, self.camera, self.pico_controller, home_routine, color)
        
    async def home(self):
        self.logger.info('Homing routine started')
        
        while True:
            self.home_routine = await self.home_routine.run()
            if not self.home_routine: break
        
        x, y, theta = self.start_positions[self.start_pos]
        self.tactic.motor_controller.set_pos(x, y, theta)
        
    def start(self):
        self.tactic.motor_controller.time_started = time()
        self.logger.info(f'Tacitc started')
        
    async def run(self) -> int | None:
        self.tactic = await self.tactic.run()
        if not self.tactic: return None
        
        return self.tactic.points

async def main():
    try:
        controller = RobotController()
        controller.set_tactic(1, 2)
        await controller.home()
        await asyncio.sleep(1)
        controller.start()
        points = 1
        while True: 
            points = await controller.run()
            if not points: break
            
        await controller.motor_controller.set_stop()
        await asyncio.sleep(0.5)
    finally:
        await controller.motor_controller.set_stop()
        controller.motor_controller.lidar.stop()
    

if __name__ == '__main__':
    asyncio.run(main())
