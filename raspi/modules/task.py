from typing import Self
from time import time, sleep
import logging
import asyncio

from modules.motor_controller import MotorController
from modules.camera import Camera
from modules.pathfinding import Pathfinder
from modules.stepper import Stepper
from modules.servos import  Servos


class Task():
    def __init__(self, motor_controller: MotorController, camera: Camera, servos: Servos, stepper: Stepper, action_set: list[list[str]], color: str):
        self.motor_controller = motor_controller
        self.camera = camera
        self.servos = servos
        self.stepper = stepper
        
        self.action_set = action_set
        self.initial_actions = self.action_set[0] # if we abort and want to add task to end
        self.actions = self.action_set.pop(0)
        
        self.color = color
                        
        self.points = 0
        
        self.logger = logging.getLogger(__name__)        
        
        self.pathfinder = Pathfinder()
    
    def next_task(self):
        self.initial_actions = self.action_set[0]
        self.actions = self.action_set.pop(0)
        
    async def perform_action(self, msg):
        cmd = msg[:2]
        match cmd:
            case 'sp':
                values = msg[2:].split(';')
                self.motor_controller.set_pos(int(values[0]), int(values[1]), int(values[2]))
            case 'cs': #check stack
                print(self.camera.check_stacks(True)) # debug oder nicht
                # gibt anzahl stacks zurück
            case 'st':  # set tactic
                start_pos, tactic = msg[2:].split(';')
                self.set_tactic(int(start_pos), int(tactic))
                self.logger.info(f"set tactic: pos:{start_pos} tactic:{tactic}")
                await self.home()
                await asyncio.sleep(1)
                asyncio.create_task(self.run_tactic())
                await asyncio.sleep(0.5)
            case 'ws': # write servo
                values = msg[2:].split(';')
                self.logger.info(f"set servo cmd: {values}")
                self.servos.write_servo(int(values[0]), int(values[1]))
            case 'ra':
                self.servos.release_all()
            case 'sl': # stepper lift
                values = msg[2:].split(';')
                self.logger.info(f"set stepper heigth XYZ: {values}")
                self.stepper.set_pos_mm(int(values[0]), int(values[1]), int(values[2]))
            case 'sh': # stepper home
                self.logger.info("homed all steppers")
                self.stepper.home()
            case 'dd': # drive distance
                self.logger.info(f"drive distance: {int(msg[2:])}")
                await self.motor_controller.drive_distance(int(msg[2:]))
            case 'dp':
                values = msg[2:].split(';')
                print(values)
                print('bassd')
                await self.motor_controller.drive_to_point(int(values[0]), int(values[1]), int(values[2]))
            case 'ta': # turn angle
                self.logger.info(f"turn angle: {int(msg[2:])}")
                await self.motor_controller.turn_angle(int(msg[2:]))
                await self.motor_controller.set_stop()
            case 'tt': # turn to
                self.logger.info(f"turn to {msg[2:]}")
                await self.motor_controller.turn_to(int(msg[2:]))
            case 'cw': # clean wheels
                self.logger.info(f"clean wheels")
                await self.motor_controller.clean_wheels()
            case 'ac': # anfahren cans
                self.logger.info("anfahren cans")
                self.servos.pos_anfahren()
                sleep(0.5)
                self.stepper.anfahren()
            case 'gc': # grip cans
                self.logger.info("grip cans")
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
                self.logger.info("emergency stop!")
            case 'hg': # home gripper (servos and steppers)
                self.servos.pos_anfahren()
                sleep(1)
                self.stepper.home()
                self.logger.info("home gripper")
            case 'hb': # home bot
                self.motor_controller.home()
                self.logger.info("home bot")
            case 'xx':
                self.motor_controller.set_pos(1700, 215, 0)
                
                self.servos.pos_anfahren()
                sleep(0.3)
                self.stepper.anfahren()
                
                # await self.motor_controller.drive_to_point(1900, 700, 0)
                # await self.motor_controller.drive_distance(200)
                
                # # seperate 1st stapel
                # self.stepper.down()
                # sleep(0.4)
                # self.servos.grip_cans()
                # sleep(0.5)
                # self.stepper.lift()
                # self.servos.servo_mitte_lift(2)
                # sleep(1)
                # self.servos.cans_in()
                                
                # # place 1st stapel
                # await self.motor_controller.drive_to_point(1700, 350, 180)
                # self.servos.release_all()
                # sleep(0.5)
                
                # await self.motor_controller.drive_distance(-200)

                # self.servos.pos_anfahren()
                # sleep(0.3)
                # self.stepper.anfahren()

                # await self.motor_controller.drive_to_point(2200, 600, 183)
                # await self.motor_controller.drive_to_point(2200, 200, 183)

                # # grip 2nd level
                # self.servos.grip_one_layer()
                # self.stepper.down()
                # sleep(0.3)
                # self.servos.servo_plate_grip(2)
                # sleep(0.2)
                # self.stepper.lift_1er()
                
                # await self.motor_controller.drive_distance(-300)
                
                # # build level
                # self.servos.cans_in()
                # self.stepper.build_1er()
                # sleep(0.2)
                # self.servos.servo_plate_grip(1)
                # sleep(0.2)
                # self.servos.servo_plate_rotate(1)
                # sleep(0.5)
                # self.stepper.lift_3er()
                # self.servos.servo_mitte_grip(1)
                
                # await self.motor_controller.drive_to_point(1700, 550, 180)
                # await self.motor_controller.drive_to_point(1700, 350, 180)
                
                # # place on top of level 2
                # self.servos.release_all()
                # sleep(1)
                # await self.motor_controller.drive_distance(-200)
                
                await self.motor_controller.drive_to_point(2575, 400, 90)
                # await self.motor_controller.drive_to_point(2600, 400, 90)
                await self.motor_controller.drive_to_point(2750, 400, 90)
                
                self.stepper.down()
                sleep(1)
                self.servos.grip_cans()
                sleep(1)
                self.stepper.lift()
                sleep(1)
                self.servos.cans_in()
                sleep(1)
                self.servos.release_all()
                sleep(1)
                
                await self.motor_controller.drive_distance(-200)
                
                self.servos.pos_anfahren()
                self.stepper.down()
                sleep(0.5)
                self.servos.servo_plate_rotate(1)
                self.servos.cans_in()
                
                await self.motor_controller.drive_distance(220)
                self.servos.grip_unten()
                self.stepper.set_pos_mm(20, 0, 20)
                

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
                self.motor_controller.set_pos(300, 300, 0)
            case 'gp':
                x, y, theta = self.motor_controller.encoder.get_pos()
                print(f'{x}, {y}, {theta}')
            case _: # default
                self.logger.info(f"Unknown msg: {msg}")
                
    async def run(self) -> Self:        
        if self.motor_controller.time_started + 96 < time():
            await self.motor_controller.set_stop()
            return None
        
        if len(self.actions) <= 0:
            if len(self.action_set) <= 0:
                return None
            
            self.next_task()
        
        current_action = self.actions.pop(0)
        
        await self.perform_action(current_action)
        sleep(0.3)
        
        return self
    