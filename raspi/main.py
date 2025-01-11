import math
import threading
import time
from data import SerialManager
from simple_pid import SimplePID
from motor_controller import MotorController

class RobotController:
    def __init__(self):        
        self.pos = [0, 0]
        
        self.x = 255
        self.y = 255
        self.theta = 0
        
        # Use threading.Event for thread synchronization
        self._stop_event = threading.Event()
        
        # Use threading.Lock for thread-safe access to shared resources
        self._lock = threading.Lock()
        
        # Create serial manager once
        self.serial_manager = SerialManager()
        
        # Create PID Controller
        self.pid = [SimplePID(), SimplePID()]
        
        self.motor_controller = MotorController()
        
        
    def serial_process(self):
        while True:
            try:
                self.serial_manager.send_pwm(self.pwm, self.dir)
                l, r, x, y, theta = self.serial_manager.get_pos()
                with self._lock:
                    self.pos = [l, r]
                    self.x = x
                    self.y = y
                    self.theta = theta
                    
            except Exception as e:
                print(f"Error in Serial process: {e}") 
                break
        
    
    def pwm_process(self):
        while True:
            try:
                with self._lock:
                    pos = self.pos
                    
                self.motor_controller.proccess_pwm(pos)
                
            except Exception as e:
                print(f"Error in PWM process: {e}") 
                break


    def run(self):
        self.drive_distance(1000)
        self.pwm_process()

def main():
    controller = RobotController()
    controller.run()

if __name__ == '__main__':
    main()