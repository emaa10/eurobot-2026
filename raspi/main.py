import random
import threading
import time
from data import SerialManager
from position import Position

class RobotController:
    def __init__(self):
        self.pos = Position(0, 0)
        self.pwm_left = (0, 0)
        self.pwm_right = (0, 0)
        
        # Use threading.Event for thread synchronization
        self._stop_event = threading.Event()
        
        # Use threading.Lock for thread-safe access to shared resources
        self._lock = threading.Lock()
        
        # Create serial manager once
        self._serial_manager = SerialManager()

    def serial_process(self):
        while not self._stop_event.is_set():
            try:
                # Use lock to safely update shared position
                with self._lock:
                    self.pos = self._serial_manager.get_pos()
                    pwm_left = self.pwm_left
                    pwm_right = self.pwm_right
                
                # Send PWM outside of lock to minimize lock time
                self._serial_manager.send_pwm(pwm_left, pwm_right)
                print(f"sent pwm {pwm_left[0]}, {pwm_left[1]}, {pwm_right[0]}, {pwm_right[1]}")
                
                # Sleep to control update frequency
                time.sleep(0.05)
            
            except Exception as e:
                print(f"Error in serial process: {e}")
                break

    def pwm_process(self):
        while not self._stop_event.is_set():
            try:
                # Generate random PWM values
                pwm_right = (random.randint(0, 255), random.randint(0, 255))
                pwm_left = (random.randint(0, 255), random.randint(0, 255))
                
                # Use lock to safely update shared PWM values
                with self._lock:
                    self.pwm_right = pwm_right
                    self.pwm_left = pwm_left
                
                # Sleep to control update frequency
                time.sleep(1)
            
            except Exception as e:
                print(f"Error in PWM process: {e}")
                break

    def run(self):
        try:
            # Create threads
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