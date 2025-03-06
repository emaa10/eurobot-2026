from modules.task import Task
from modules.motor_controller import MotorController
from modules.drive_state import DriveState
from modules.lidar import Lidar

import math

class RobotController:
    def __init__(self):
        self.x = 255
        self.y = 255
        self.theta = 0
        
        self.stopping = False
        
        self.motor_controller = MotorController()
        
        self.lidar = Lidar('/dev/ttyUSB0')
        
        self.task = Task(self.motor_controller, actions=['d300'])
        
        
    def add_task(self, actions: list[str]):
        task = Task(self.motor_controller, actions=actions)
        self.task.add_task(task)
        
        
    def control_loop(self, state: DriveState, latest_scan: list[tuple]):
        self.x = state.x
        self.y = state.y
        self.theta = state.theta
        
        for angle, distance in latest_scan:
            d_x = distance * math.cos(angle * math.pi / 180)
            d_y = distance * math.sin(angle * math.pi / 180)
        
        if state.finished:
            self.task = self.task.next_action()
            
        return True if not self.task else False
            

    def run(self):
        try:
            print("Starting Lidar scanning")
            if not self.lidar.start_scanning():
                print("Failed to start Lidar")
                return
        
            # Main loop
            while True:
                # Get the latest scan with timeout
                latest_scan = self.lidar.get_latest_scan(timeout=0.5)
                state = self.motor_controller.pwm_loop()
                if self.control_loop(state, latest_scan): break
                
                # Check if Lidar thread is still running
                if not self.lidar.is_running():
                    print("Lidar thread stopped unexpectedly")
                    break
    
        except KeyboardInterrupt:
            print("Interrupted by user")
    
        finally:
            print("Stopping Lidar...")
            self.lidar.stop()

def main():
    controller = RobotController()
    controller.run()

if __name__ == '__main__':
    main()
