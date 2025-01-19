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
        
        self.motor_controller = MotorController(self.serial_manager)
        
        
    def serial_process(self):
        while True:
            try:
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
        self.motor_controller.drive_distance(500)
        while True:
            try:
                with self._lock:
                    pos = self.pos
                    
                self.motor_controller.proccess_pwm(pos)
                
            except Exception as e:
                print(f"Error in PWM process: {e}") 
                break


    def run(self):
        try:
            serial_thread = threading.Thread(target=self.serial_process, daemon=True)
            pwm_thread = threading.Thread(target=self.pwm_process, daemon=True)
            
            # Start threads
            serial_thread.start()
            pwm_thread.start()

        
            # Wait for keyboard interrupt
            while not self._stop_event.is_set():
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("Stopping threads")
        
        finally:
            # Signal threads to stop
            self._stop_event.set()
            
            # Optional: Wait for threads to finish with a timeout
            serial_thread.join(timeout=2)
            pwm_thread.join(timeout=2)
            
            print("All threads stopped")

def main():
    controller = RobotController()
    controller.run()

if __name__ == '__main__':
    main()