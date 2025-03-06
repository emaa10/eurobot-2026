import asyncio
from modules.task import Task
from modules.motor_controller import MotorController
from modules.drive_state import DriveState
from modules.lidar_test import Lidar

class RobotController:
    def __init__(self, lidar_port='/dev/tty.usbserial-0001'):
        self.x = 255
        self.y = 255
        self.theta = 0
        
        self.motor_controller = MotorController()
        
        # Initialize Lidar
        self.lidar = Lidar(lidar_port)
        
        # Initial task sequence
        self.task = Task(self.motor_controller, actions=['t90', 'd200', 'p655;255;0', 'd300'])
        
        # Flag to track obstacle detection
        self.obstacle_detected = False
    
    async def lidar_monitoring_loop(self):
        """
        Continuously monitor Lidar in the background
        """
        while True:
            try:
                # Check for obstacles
                is_clear = await self.lidar.async_process_scan()
                
                # Update obstacle detection state
                self.obstacle_detected = not is_clear
                
                if self.obstacle_detected:
                    print("Obstacle detected! Pausing/adjusting navigation.")
            
            except Exception as e:
                print(f"Lidar monitoring error: {e}")
                await asyncio.sleep(1)
    
    async def control_loop(self, state: DriveState):
        """
        Main control loop with Lidar integration
        """
        # Update robot state
        self.x = state.x
        self.y = state.y
        self.theta = state.theta
        
        # Check for obstacles
        if self.obstacle_detected:
            # Implement obstacle avoidance strategy
            # For example:
            print("Obstacle in path. Stopping or changing course.")
            # self.motor_controller.stop()  # Stop motors
            # self.task = self.alternative_route_task()  # Plan alternative route
            return False
        
        # Normal task progression
        if state.finished:
            self.task = self.task.next_action()
        
        return True if not self.task else False
    
    async def run(self):
        """
        Main robot run method with concurrent Lidar monitoring
        """
        # Connect Lidar
        await self.lidar.connect()
        
        try:
            # Start Lidar monitoring as a background task
            lidar_task = asyncio.create_task(self.lidar_monitoring_loop())
            
            # Main control loop
            while True:
                state = self.motor_controller.pwm_loop()
                
                # Run control loop
                if not await self.control_loop(state):
                    break
        
        finally:
            # Ensure Lidar is closed
            await self.lidar.close()
            
            # Cancel Lidar monitoring task
            lidar_task.cancel()

async def main():
    """
    Main async entry point
    """
    controller = RobotController()
    await controller.run()

if __name__ == '__main__':
    asyncio.run(main())