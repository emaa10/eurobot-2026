from modules.task import Task
from modules.camera import Camera
from modules.motor_controller import MotorController
from modules.pico_com import Pico

import RPi.GPIO as GPIO
import asyncio
from time import time
import logging
import socket
import threading
import sys

pullcord = 22

HOST = '127.0.0.1'
PORT = 5001

client_socket = None

class RobotController:
    def __init__(self):
        CAM = False
        GUI = True

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pullcord, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self.start_pos = 0
        self.points = 0
        
        logging.basicConfig(filename='/home/eurobot/main-bot/raspi/eurobot.log', level=logging.INFO)
        self.logger = logging.getLogger(__name__)
                
        self.motor_controller = MotorController()
        self.camera = Camera() if CAM else None
        self.pico_controller = Pico()

        self.pico_controller.set_command('i', 0)
        # !! muss des hier?

        if CAM:
            self.camera.start()
            self.logger.info("Camera started")
                    
        self.tactic: Task | None = None
        self.home_routine: Task | None = None
                
        self.start_positions = {
            # gelb
            1: [200, 850, 90],
            2: [1200, 150, 0],
            3: [450, 1800, 180],
            # blau
            4: [1550, 1800, 180],
            5: [1800, 150, 0],
            6: [2800, 850, 270],
        }
        
        self.home_routines = {
            1: [['hh', 'dd50', 'ta-90', 'hh', 'dd100']],
            2: [['hh', 'ta-90', 'hh', 'dd50']],
            3: [['hh', 'dd100']],
            4: [['hh', 'dd100']],
            5: [['hh', 'ta90', 'hh', 'dd50']],
            6: [['hh', 'dd50', 'ta90', 'hh', 'dd100']],

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
        }
        

    def get_commands(self, client_socket, address):
        try:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    print(f"Client {address} disconnected")
                    break
                    
                message = data.decode().strip()
                print(f"Received from {address}: {message}")
                cmd = message[0]
                if cmd == "t":
                    startpos = int(message[1:message.index(",")])
                    tactic = int(message[message.index(",")+1:])
                    print(f"Tactic set: Startpos: {startpos} - tactic: {tactic}")
                elif cmd == "p":
                    pcmd = message[1:]
                    print(f"pico command: {pcmd}")
                elif cmd == "d":
                    dist = int(message[1:])
                    print(f"drive distance: {dist}")
                elif cmd == "a":
                    angle = int(message[1:])
                    print(f"angle: {angle}")
                elif cmd == "e0":
                    print("emergency stop")
                else:
                    print(f"got shit: {message}")
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()

    # h: homing done
    # p: pullcord pulled
    # c<count>: set count points
    def send_message(self, client_socket, msg: str):
        """Send a string message to the connected client"""
        try:
            client_socket.sendall(msg.encode())
            print(f"Sent to client: {msg}")
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False

    def start_server(self):
        global client_socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_socket.bind((HOST, PORT))
            server_socket.listen(5)
            print(f"Server running on {HOST}:{PORT}")
            
            while True:
                client_socket, address = server_socket.accept()
                print(f"Connected to client at {address}")
                client_handler = threading.Thread(
                    target=self.get_commands,
                    args=(client_socket, address),
                    daemon=True
                )
                client_handler.start()
        except KeyboardInterrupt:
            print("Server shutting down...")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            server_socket.close()
            print("Server stopped")


    def set_tactic(self, start_pos_num: int, tactic_num: int):
        color = 'yellow' if start_pos_num <= 3 else 'blue'
        self.start_pos = start_pos_num
        
        tactic = self.tactix_blue[tactic_num] if color == 'blue' else self.tactix_yellow[tactic_num]
        
        print(tactic)
        home_routine = self.home_routines[start_pos_num]
        
        self.logger.info(f'color: {color}, tactic: {tactic}, home_routine: {home_routine}, startpos: {start_pos_num}')
                
        self.tactic = Task(self.motor_controller, self.camera, self.pico_controller, tactic, color)
        self.home_routine = Task(self.motor_controller, self.camera, self.pico_controller, home_routine, color)
        
    async def home(self):
        self.logger.info('Homing routine started')
        
        self.pico_controller.home_pico()
        
        while True:
            self.home_routine = await self.home_routine.run()
            if not self.home_routine: break
        
        x, y, theta = self.start_positions[self.start_pos]
        self.tactic.motor_controller.set_pos(x, y, theta)
        
        self.logger.info('Homing done')
        
    def start(self):
        self.tactic.motor_controller.time_started = time()
        self.tactic.motor_controller.gegi = True
        self.logger.info(f'Tacitc started')
        
    async def run(self) -> int:
        self.tactic = await self.tactic.run()
        if not self.tactic: 
            self.logger.info(f'Tactic complete')
            return -1
        
        return self.tactic.points

# main bot loop now
async def main():
    controller = RobotController()
    if len(sys.argv) > 1:
        controller.GUI = False
        cmd = sys.argv[1]
        print(controller.process_command(cmd))
    else:
        controller.GUI = True
        controller.run_listener()

if __name__ == '__main__':
    asyncio.run(main())
