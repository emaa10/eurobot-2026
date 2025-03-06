from modules.task import Task
from modules.motor_controller import MotorController
from modules.drive_state import DriveState
from modules.lidar import Lidar

import math
from time import time_ns

class RobotController:
    def __init__(self):
        self.x = 255
        self.y = 255
        self.theta = 0
                
        self.motor_controller = MotorController()
        
        self.lidar = Lidar('/dev/ttyUSB0')
        
        self.task = Task(self.motor_controller, actions=['d600'])
        
        
    def add_task(self, actions: list[str]):
        task = Task(self.motor_controller, actions=actions)
        self.task.add_task(task)
        
        
    def control_loop(self, state: DriveState, latest_scan: list[tuple] | None = None):
        # update pos
        self.x = state.x
        self.y = state.y
        self.theta = state.theta
        
        # lidar
        stopped = False
        
        if latest_scan:
            for angle, distance in latest_scan:
                # point in relation to bot
                d_x = distance * math.sin(angle * math.pi / 180)
                d_y = distance * math.cos(angle * math.pi / 180)
                
                # point in arena
                arena_angle = (-angle) + self.theta
                arena_x = distance * math.cos(arena_angle * math.pi / 180) + self.x
                arena_y = distance * math.sin(arena_angle * math.pi / 180) + self.y
                
                point_in_arena = 50 <= arena_x <= 2950 and 50 <= arena_y <= 1950    # 5cm threshold
                point_in_arena = True
                            
                if (state.direction >= 0 and 0 <= d_y <= 500) and abs(d_x) <= 250 and point_in_arena:
                    stopped = True
                    print(f'Obstacle: x: {d_x}, y: {d_y}, angle: {angle}, distance: {distance}')
                    break
                
                if  (state.direction <= 0 and 0 >= d_y >= -500) and abs(d_x) <= 250 and point_in_arena:
                    stopped = True
                    print(f'Obstacle: x: {d_x}, y: {d_y}, angle: {angle}, distance: {distance}')
                    break
                
        
            self.motor_controller.stopped = stopped
        
        # task management
        if state.finished:
            self.task = self.task.next_action(self.x, self.y)
            
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
