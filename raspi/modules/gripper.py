from modules.stepper import Stepper
from modules.servos import Servos

from time import sleep

class Gripper:
    def __init__(self) -> None:
        self.servos = Servos()
        self.stepper = Stepper()
        
    def home(self):
        self.servos.pos_anfahren(True)
        sleep(1)
        self.stepper.home()
        sleep(8)
        self.stepper.set_pos_mm(15,0,200)
        sleep(1)
        self.pos_home()
        
    def pos_home(self):
        self.servos.servo_plate_rotate(1)
        sleep(1)
        self.servos.grip_außen()
        self.servos.gripper_in()
        self.servos.servo_plate_grip(2)
        self.servos.servo_left_rotate(5)
        self.servos.servo_right_grip(3)
        self.servos.servo_flag(1)
    
    # anfahren stack from arena
    def anfahren(self, first_time = False):
        self.servos.pos_anfahren(first_time)
        sleep(0.3)
        self.stepper.pos_anfahren()
        
    # build lvl2 from stack in arena
    def build_2er(self):
        self.stepper.down()
        sleep(0.4)
        self.servos.grip_cans()
        sleep(0.5)
        self.servos.gripper_out()
        sleep(0.5)
        self.stepper.lift()
        sleep(1)
        self.servos.gripper_in()
        sleep(0.85)
        self.servos.servo_mitte_lift(2)
    
    # grips one layer from arena stack
    def grip_one_layer(self):
        self.servos.servo_left_grip(2)
        self.servos.servo_right_grip(2)
        self.stepper.down()
        sleep(1)
        self.servos.servo_plate_grip(2)
        self.servos.servo_left_rotate(1)
        self.servos.servo_right_rotate(1)
        sleep(1)
        self.stepper.seperate_1er()
    
    # build a lvl 1 stack 
    def build_one_layer(self):
        self.servos.gripper_in()
        sleep(1)
        self.stepper.build_1er()
        self.servos.servo_mitte_grip(1)
    
    # grip a stack at the bottom
    def grip_unten(self):
        self.stepper.down()
        self.servos.servo_plate_rotate(1)
        sleep(0.7)
        self.servos.servo_left_rotate(2)
        self.servos.servo_right_rotate(2)
        self.servos.servo_mitte_lift(1)
        self.servos.servo_mitte_grip(1)
        self.servos.servo_left_grip(1)
        self.servos.servo_right_grip(1)
        self.servos.servo_left_rotate(4)
        self.servos.servo_right_rotate(4)
    
    def lift_3er(self):
        self.servos.servo_plate_grip(1)
        sleep(0.3)
        self.servos.servo_plate_rotate(1)
        sleep(0.5)
        self.stepper.lift_3er()
    
    def release(self):
        self.servos.release_all()
        
def main():
    gripper = Gripper()
    gripper.home()
    
if __name__ == '__main__':
    main()