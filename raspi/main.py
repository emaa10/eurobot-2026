import asyncio
import sys
import RPi.GPIO as GPIO
import logging
from time import time, sleep
import signal

from modules.task import Task
from modules.camera import Camera
from modules.motor_controller import MotorController
from modules.servos import Servos
from modules.stepper import Stepper

HOST = '127.0.0.1'
PORT = 5001
pullcord = 22

class RobotController:
    def __init__(self):
        self.CAM = True

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pullcord, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self.start_pos = 0
        self.points = 0
        self.client_writer: asyncio.StreamWriter | None = None

        logging.basicConfig(filename='/home/eurobot/main-bot/raspi/eurobot.log', level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.motor_controller = MotorController()
        self.camera = Camera() if self.CAM else None
        self.servos = Servos()
        self.stepper = Stepper()

        if self.CAM:
            self.camera.start()
            self.logger.info("Camera started")

        self.tactic = Task(self.motor_controller, self.camera, self.servos, self.stepper, [[]], 'blue')
        self.home_routine = Task(self.motor_controller, self.camera, self.servos, self.stepper, [[]], 'blue')

        self.start_positions = {
            # gelb
            1: [200, 850, 90],
            2: [1200, 150, 0],
            3: [450, 1800, 180],
            # blau
            4: [1550, 1800, 180],
            5: [1800, 150, 0],
            6: [2800, 850, 270],
            7: [100, 100, 0],
        }
        self.home_routines = {
            1: [['hh', 'dd50', 'ta-90', 'hh', 'dd100']],
            2: [['hh', 'ta-90', 'hh', 'dd50']],
            3: [['hh', 'dd100']],
            4: [['hh', 'dd100']],
            5: [['hh', 'ta90', 'hh', 'dd50']],
            6: [['hh', 'dd50', 'ta90', 'hh', 'dd100']],
            7: [['hh']],
        }
        self.tactix_yellow = {
            1: [['hh', 'fd', 'dd400', 'ip20', 'dp1100;650;0', 'pg', 'dp1100;750;0', 'gs', 'dd-100', 'dp1250;400;180', 'ds', 'ip12', 'dd-200', 'dp790;500;180', 'dp790;200;180', 'ip4', 'dd-200'], ['dh']], # full takitk
            2: [['hh', 'fd', 'dd400', 'ip20', 'dp1100;650;0', 'pg', 'dp1100;750;0', 'gs', 'dd-100', 'dp1250;400;180', 'ds', 'ip12', 'dd-200', 'ge'], ['dh']], # goat
            3: [['hh', 'fd', 'dd400', 'ip20'], ['dp400;1360;270', 'pg', 'dp270;1350;270', 'gs', 'dd-100', 'dp400;1720;0', 'ds', 'ip12', 'dd-200', 'ge']], # keine ahnung
            4: [['hh', 'fd', 'dd400', 'ip20'], ['dh']], # safe
        }
        self.tactix_blue = {
            1: [['hh', 'fd', 'dd400', 'ip20', 'dp1900;650;0', 'pg', 'dp1900;750;0', 'gs', 'dd-100', 'dp1750;400;180', 'ds', 'ip12', 'dd-200', 'dp2250;500;180', 'dp2250;200;180', 'ip4', 'dd-200'], ['dh']], # full takitk
            2: [['hh', 'fd', 'dd400', 'ip20', 'dp1900;650;0', 'pg', 'dp1900;750;0', 'gs', 'dd-100', 'dp1750;400;180', 'ds', 'ip12', 'dd-200', 'ge'], ['dh']], # goat
            3: [['hh', 'fd', 'dd400', 'ip20'], ['dp400;1360;270', 'pg', 'dp270;1350;270', 'gs', 'dd-100', 'dp400;1720;0', 'ds', 'ip12', 'dd-200', 'ge']], # keine ahnung
            4: [['hh', 'fd', 'dd400', 'ip20'], ['dh']], # safe
            5: [['dd100'], ['ta90', 'dp400;400;0']]
        }

    def l(self, msg: str):
        print(msg)
        self.logger.info("MAIN - " + msg)

    async def get_command(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        self.l(f"Connected to client at {addr}")
        self.client_writer = writer
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    self.l(f"Client {addr} disconnected")
                    break
                msg = data.decode().strip()
                self.l(f"Received from {addr}: {msg}")
                await self.tactic.perform_action(msg)
        except Exception as e:
            self.l(f"Error {e} with client {addr}")
        finally:
            writer.close()
            await writer.wait_closed()
            self.client_writer = None

    # h: homing done
    # p: pullcord pulled
    # c<count>: set count points
    async def send_message(self, msg: str) -> bool:
        if not self.client_writer: return False
        try:
            self.client_writer.write(msg.encode())
            await self.client_writer.drain()
            self.l(f"Sent: {msg}")
            return True
        except Exception as e:
            self.l(f"Send error: {e}")
            return False

    async def start_server(self):
        server = await asyncio.start_server(self.get_command, HOST, PORT)
        self.l(f"Server running on {HOST}:{PORT}")
        async with server:
            await server.serve_forever()

    def set_tactic(self, start_pos_num: int, tactic_num: int):
        color = 'yellow' if start_pos_num <= 3 else 'blue'
        self.start_pos = start_pos_num
        
        tactic = self.tactix_blue[tactic_num] if color == 'blue' else self.tactix_yellow[tactic_num]
        
        self.l(tactic)
        home_routine = self.home_routines[start_pos_num]
        
        self.l(f'color: {color}, tactic: {tactic}, home_routine: {home_routine}, startpos: {start_pos_num}')
                
        self.tactic = Task(self.motor_controller, self.camera, tactic, color)
        self.home_routine = Task(self.motor_controller, self.camera, home_routine, color)

    async def run_tactic(self):
        self.start()
        while True:
            points = await self.run()
            await self.send_message(f"c{points}")
            if points == -1: 
                break
        await self.motor_controller.set_stop()
        
    async def home(self):
        self.l('Homing routine started')
        
        while True:
            self.home_routine = await self.home_routine.run()
            if not self.home_routine: break
        
        x, y, theta = self.start_positions[self.start_pos]
        self.tactic.motor_controller.set_pos(x, y, theta)
        
        self.l('Homing done')
        await self.send_message('h')

    def start(self):
        self.tactic.motor_controller.time_started = time()
        self.tactic.motor_controller.gegi = True
        self.l(f'Tactic started')
        
    async def run(self) -> int:
        if not self.tactic:
            return -1
            
        self.tactic = await self.tactic.run()
        if not self.tactic: 
            self.l(f'Tactic complete')
            return -1
        return self.tactic.points
        
    async def cleanup(self):
        """Clean up all resources before exit"""
        self.logger.info("Starting cleanup...")
        
        # Stop the motor controller
        await self.motor_controller.set_stop()
        
        # Stop the lidar
        if self.motor_controller.lidar:
            self.motor_controller.lidar.stop()
            
        # Release all servos
        if self.servos:
            self.servos.release_all()
            
        # Clean up GPIO
        GPIO.cleanup()
        
        self.logger.info("Cleanup completed")

# main bot loop now
async def main():
    controller = RobotController()
    
    # Set up signal handler
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown(controller)))
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown(controller)))
    
    try:
        await controller.start_server()
    except Exception as e:
        controller.logger.error(f"Error in main loop: {e}")
        await controller.cleanup()

async def shutdown(controller):
    """Handle shutdown gracefully"""
    controller.logger.info("Shutdown initiated")
    await controller.cleanup()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    loop = asyncio.get_running_loop()
    loop.stop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Shutting down')
