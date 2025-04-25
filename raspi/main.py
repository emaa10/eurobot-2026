from modules.task import Task
from modules.motor_controller import MotorController
from modules.drive_state import DriveState
from modules.lidar import Lidar
from modules.camera import Camera

import math
import asyncio

LIDAR = False
CAM = False

class RobotController:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.theta = 0.0
        
        self.motor_controller = MotorController()
                        
        self.lidar = Lidar('/dev/ttyUSB0') if LIDAR else None
        
        self.task = Task(actions=[['dd500'], ['ta90'], ['ta90']])
        
    def add_task(self, actions: list[str]):
        task = Task(actions=actions)
        self.task.add_task(task)
        
    async def control_loop(self, state: DriveState, latest_scan: list[tuple] | None = None):
        # update pos
        self.x = state.x
        self.y = state.y
        self.theta = state.theta
        
        # lidar
        stop = False
            
        if not latest_scan:
            return True if not self.task else False
        
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
                stop = True
                print(f'Obstacle: x: {d_x}, y: {d_y}, angle: {angle}, distance: {distance}')
                break
            
            if  (state.direction <= 0 and 0 >= d_y >= -500) and abs(d_x) <= 250 and point_in_arena:
                stop = True
                print(f'Obstacle: x: {d_x}, y: {d_y}, angle: {angle}, distance: {distance}')
                break
                
        self.motor_controller.stop = stop   

    async def run(self):
        try:
            if not self.lidar.start_scanning() and LIDAR:
                print("Failed to start Lidar")
                return
            
            self.task = await self.task.next_action(self.x, self.y)
            
            while True:
                latest_scan = self.lidar.get_latest_scan() if LIDAR else None
                state = await self.task.control_loop()
                
                self.x = state.x
                self.y = state.y
                self.theta = state.theta
                self.task = state.task
                
                await self.control_loop(state, latest_scan)
                if state.finished: break
                
                if LIDAR and not self.lidar.is_running():
                    print("Lidar thread stopped unexpectedly")
                    break        
    
        except KeyboardInterrupt:
            print("Interrupted by user")
    
        finally:
            print("Stopping Lidar...")
            if LIDAR: self.lidar.stop()

async def main():
    controller = RobotController()
    await controller.run()
    # print(Camera.get_distance())

if __name__ == '__main__':
    asyncio.run(main())
