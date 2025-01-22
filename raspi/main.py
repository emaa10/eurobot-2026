from data import SerialManager
from motor_controller import MotorController

class RobotController:
    def __init__(self):
        # Create serial manager once
        self.serial_manager = SerialManager()
        
        # Create motor_controller
        self.motor_controller = MotorController(self.serial_manager)


    def run(self):
        self.motor_controller.drive_distance(400)
        self.motor_controller.pwm_process()
        self.motor_controller.turn_angle(-90)
        self.motor_controller.pwm_process()
        self.motor_controller.drive_distance(400)
        self.motor_controller.pwm_process()
        self.motor_controller.turn_angle(-90)
        self.motor_controller.pwm_process()
        self.motor_controller.drive_distance(400)
        self.motor_controller.pwm_process()
        self.motor_controller.turn_angle(-90)
        self.motor_controller.pwm_process()
        self.motor_controller.drive_distance(400)
        self.motor_controller.pwm_process()
        self.motor_controller.turn_angle(-90)
        self.motor_controller.pwm_process()

def main():
    controller = RobotController()
    controller.run()

if __name__ == '__main__':
    main()
