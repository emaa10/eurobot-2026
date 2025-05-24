import asyncio
import sys
import RPi.GPIO as GPIO
import logging
from time import time, sleep

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
                cmd = msg[:2]
                match cmd:
                    case 'cs':
                        # check stack
                        print(self.camera.check_stacks(int(msg[2]), True))
                    case 'st':  # set tactic
                        start_pos, tactic = msg[2:].split(';')
                        self.set_tactic(int(start_pos), int(tactic))
                        self.l(f"set tactic: pos:{start_pos} tactic:{tactic}")
                        await self.home()
                        await asyncio.sleep(1)
                        asyncio.create_task(self.run_tactic())
                        await asyncio.sleep(0.5)
                    case 'ws': # write servo
                        values = msg[2:].split(';')
                        self.l(f"set servo cmd: {values}")
                        self.servos.write_servo(int(values[0]), int(values[1]))
                    case 'sl': # stepper lift
                        values = msg[2:].split(';')
                        self.l(f"set stepper heigth XYZ: {values}")
                        self.stepper.set_pos_mm(int(values[0]), int(values[1]), int(values[2]))
                    case 'sh': # stepper home
                        self.l("homed all steppers")
                        self.stepper.home()
                    case 'dd': # drive distance
                        self.l(f"drive distance: {int(msg[2:])}")
                        await self.motor_controller.drive_distance(int(msg[2:]))
                    case 'ta': # turn angle
                        self.l(f"turn angle: {int(msg[2:])}")
                        await self.motor_controller.turn_angle(int(msg[2:]))
                        await self.motor_controller.set_stop()
                    case 'cw': # clean wheels
                        self.l(f"clean wheels")
                        await self.motor_controller.clean_wheels()
                    case 'ac': # anfahren cans
                        self.l("anfahren cans")
                        self.servos.pos_anfahren()
                        sleep(0.5)
                        self.stepper.anfahren()
                    case 'gc': # grip cans
                        self.l("grip cans")
                        self.stepper.down()
                        sleep(1)
                        self.servos.grip_cans()
                        sleep(0.5)
                        self.stepper.lift()
                        sleep(1)
                        self.servos.cans_in()
                        self.servos.pos_wegfahren()
                    case 'es': # emergency stop
                        await self.motor_controller.set_stop()
                        self.l("emergency stop!")
                    case 'hg': # home gripper (servos and steppers)
                        self.servos.pos_anfahren()
                        sleep(1)
                        self.stepper.home()
                        self.l("home gripper")
                    case 'hb': # home bot
                        self.motor_controller.home()
                        self.l("home bot")
                    case 'xx':
                        self.servos.pos_anfahren()
                        sleep(0.7)
                        self.stepper.anfahren()

                        self.motor_controller.set_pos()
                        
                        await self.motor_controller.drive_distance(350)
                        await self.motor_controller.turn_angle(90)
                        await self.motor_controller.drive_distance(200)
                        await self.motor_controller.turn_angle(-90)
                        await self.motor_controller.drive_distance(350)
                        
                        # get 1st stapel
                        self.stepper.down()
                        sleep(1)
                        self.servos.grip_cans()
                        sleep(0.5)
                        self.stepper.lift()
                        sleep(1)
                        self.servos.cans_in()
                        sleep(0.3)
                        self.servos.pos_wegfahren()
                        
                        sleep(1)
                        
                        await self.motor_controller.turn_angle(-165)
                        await self.motor_controller.drive_distance(550)
                        await self.motor_controller.turn_angle(-18)
                        self.servos.release_all()
                        sleep(0.5)
                        await self.motor_controller.drive_distance(-200)
                        await self.motor_controller.turn_angle(-90)

                        self.servos.pos_anfahren()
                        sleep(0.3)
                        self.stepper.anfahren()

                        await self.motor_controller.drive_distance(500)

                        await self.motor_controller.turn_angle(90)
                        await self.motor_controller.drive_distance(300)

                        # grip 2nd level
                        self.stepper.down()
                        sleep(1)
                        self.servos.grip_one_layer()
                        sleep(2)
                        self.stepper.lift_1er()
                        sleep(1)
                        
                        await self.motor_controller.drive_distance(-300)
                        
                        self.servos.cans_in()
                        sleep(1)
                        self.servos.servo_plate_grip(1)
                        sleep(0.5)
                        self.servos.servo_plate_rotate(1)
                        sleep(1)
                        self.stepper.lift_3er()

                        self.servos.servo_mitte_grip(1)
                        
                        await self.motor_controller.turn_angle(90)
                        await self.motor_controller.drive_distance(500)
                        await self.motor_controller.turn_angle(-90)
                        await self.motor_controller.drive_distance(200)
                        self.servos.release_all()
                        sleep(1)
                        await self.motor_controller.drive_distance(-200)
                        
                    case 'yy':
                        self.servos.pos_anfahren()
                        sleep(0.7)
                        self.stepper.anfahren()
                        
                        await self.motor_controller.drive_distance(375)
                        await self.motor_controller.turn_angle(90)
                        await self.motor_controller.drive_distance(400)
                        
                        # get 1st stapel
                        # self.stepper.down()
                        # sleep(1)
                        # self.servos.grip_cans()
                        # sleep(0.5)
                        # self.stepper.lift()
                        # sleep(1)
                        # self.servos.cans_in()
                        # self.servos.pos_wegfahren()
                        
                        # sleep(15)
                        
                        # get 1st stapel
                        # self.stepper.down()
                        # sleep(1)
                        # self.servos.grip_cans()
                        # sleep(0.5)
                        # self.stepper.lift()
                        # sleep(1)
                        # self.servos.cans_in()
                        # self.servos.pos_wegfahren()
                        
                    case 'ra':
                        self.servos.release_all()
                    case 'tt':
                        self.servos.pos_anfahren()
                        sleep(1)
                        self.stepper.home()
                        sleep(1)
                        self.servos.start_position()
                    case 'b3': # 3er stapel
                        await self.motor_controller.drive_distance(300)
                        await self.motor_controller.turn_angle(90)
                        await self.motor_controller.drive_distance(500)
                        
                        # get 1st stapel
                        self.stepper.down()
                        sleep(1)
                        self.servos.grip_cans()
                        sleep(0.5)
                        self.stepper.lift()
                        sleep(1)
                        self.servos.cans_in()
                        self.servos.pos_wegfahren()
                        
                        # place 2nd lvl1
                        self.stepper.down()
                        sleep(1)
                        self.servos.place_1er(2)
                        sleep(0.5)
                        await self.motor_controller.drive_distance(-200)
                        
                        # get 2nd stapel
                        await self.motor_controller.turn_angle(180)
                        self.servos.pos_anfahren()
                        sleep(1)
                        self.stepper.anfahren()
                        sleep(1)
                        await self.motor_controller.drive_distance(200)
                        sleep(10)
                        
                        # grip cans
                        self.stepper.down()
                        sleep(1)
                        self.servos.grip_cans()
                        sleep(1)
                        self.stepper.lift()
                        sleep(1)
                        self.servos.cans_in()
                        sleep(0.5)
                        
                        # release
                        self.servos.place_2er()
                        
                        await self.motor_controller.drive_distance(-150)
                        
                        # grip unten
                        self.stepper.down()
                        sleep(1)
                        
                        await self.motor_controller.drive_distance(200)
                        
                        self.servos.grip_unten()
                        sleep(1)
                        self.stepper.place3er()
                        sleep(1)
                        
                        # drive onto other
                        await self.motor_controller.turn_angle(180)
                        await self.motor_controller.drive_distance(500)
                        self.servos.release_außen()
                        sleep(0.5)
                        await self.motor_controller.drive_distance(-300)
                    case 'rp':
                        self.motor_controller.set_pos(0,0,0)
                    case _: # default
                        self.l(f"Unknown msg: {msg}")
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
        
# main bot loop now
async def main():
    controller = RobotController()
    await controller.start_server()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Shutting down')