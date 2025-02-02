from data import SerialManager
from motor_controller import MotorController
from classes.DriveState import DriveState
from classes.Task import Task

class RobotController:
    def __init__(self):
        self.x = 255
        self.y = 255
        self.theta = 0
        
        # Create serial manager once
        self.serial_manager = SerialManager()
        
        # Create motor_controller
        self.motor_controller = MotorController(self.serial_manager)
        
        self.task = Task(self.motor_controller, actions=['t90', 'd200', 'p655;255;0', 'd300'])
        
    def add_task(self, actions: list[str]):
        task = Task(self.motor_controller, actions=actions)
        self.task.add_task(task)
        
    def control_loop(self, state: DriveState):
        self.x = state.x
        self.y = state.y
        self.theta = state.theta
        
        if state.finished:
            self.task = self.task.next_action()
            
        return True if not self.task else False
            

    def run(self):
        while True:
            state = self.motor_controller.pwm_loop()
            if self.control_loop(state): break

def main():
    controller = RobotController()
    controller.run()

if __name__ == '__main__':
    main()
