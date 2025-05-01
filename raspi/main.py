from modules.task import Task
from modules.camera import Camera
from modules.task_presets import TaskPresets
from modules.motor_controller import MotorController

import math
import asyncio
from time import time
import logging


class RobotController:
    def __init__(self):
        CAM = True
        
        self.start_pos
        self.points = 0
        
        logging.basicConfig(filename='/home/eurobot/main-bot/raspi/eurobot.log', level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.time_started = time()
        
        self.motor_controller = MotorController()
        self.camera = Camera() if CAM else None

        if CAM:
            self.camera.start()
            self.logger.info("Camera started")
                    
        self.tactic: Task | None = None
        self.home_routine: Task | None = None
        
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
        self.start_pos = self.start_positions[start_pos]
        self.task_presets.color = 'yellow' if start_pos <= 3 else 'blue'
        
        tactic = self.tactix[tactic]
        home_routine = self.home_routines[start_pos]
        
        self.tactic = Task(self.motor_controller, self.camera, tactic)
        self.home_routine = Task(self.motor_controller, self.camera, home_routine)
        
    async def home(self):
        self.logger.info('Homing routine started')
        
        while True:
            self.home_routine = await self.home_routine.run()
            if not self.home_routine: break
            
        self.tactic.motor_controller.set_pos(self.start_pos)
        
    async def run(self) -> int | None:
        self.task.motor_controller.time_started = time()
        self.logger.info(f'Tacitc started')
    
        self.tactic = await self.tactic.run()
        if not self.tactic: return None
        
        return self.tactic.points

async def main():
    try:
        controller = RobotController()
        controller.set_tactic(1, 1)
        await controller.home()
        points = 1
        while True: 
            points = await controller.run()
            if not points: break

    finally:
        await controller.task.motor_controller.set_stop()
        await asyncio.sleep(0.5)
    

if __name__ == '__main__':
    asyncio.run(main())
