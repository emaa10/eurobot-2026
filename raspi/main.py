import math
import threading
import time
from data import SerialManager
from trajectory_follower import TrajectoryFollower
from simple_pid import SimplePID

class RobotController:
    def __init__(self):
        self.x = 255
        self.y  = 255
        self.theta = 0
        
        self.extrax = 0
        self.extray = 0
        self.extraTheta = 0
        
        self.pwm = [0, 0]
        self.dir = [0, 0]
        
        self.NMOTORS = 2
        self.pwmCutoff = 10 # Set minimum drivable pwm value
        self.pulsesCutoff = 4
        self.pwmMax = 254
        self.currentPwm = 254
        self.lastpwm = 0
        self.lastPos = [0, 0]
        self.target = [0, 0]

        self.pulsesPerEncRev = 1200
        self.encWheelDiameterCM = 5
        self.motorWheelDiameterCM = 7
        self.encWheelScope = self.encWheelDiameterCM * math.pi
        self.motorWheelScope = self.motorWheelDiameterCM * math.pi   # distance travelled per rev
        self.pulsesPerRev = self.pulsesPerEncRev * (self.motorWheelScope / self.encWheelScope)
        self.pulsesPerMM = self.pulsesPerRev / self.motorWheelScope / 10
        self.pulsesPerCM = self.pulsesPerRev / self.motorWheelScope
        self.pwmSpeed = 100                         # default pwm speed
        self.pulsesPerSec = self.pulsesPerRev       # goal pulses per sec 1680, 1 round per second
        self.wheelDistance = 127.5                  # abstand der encoderräder in mm, muss vllt geändert werden
        self.wheelDistanceBig = 204                 # in mm, muss vllt geändert werden

        self.pulsesValue = self.pulsesPerMM
        
        self.stopped = False
        self.is_driving = False

        
        # Use threading.Event for thread synchronization
        self._stop_event = threading.Event()
        
        # Use threading.Lock for thread-safe access to shared resources
        self._lock = threading.Lock()
        
        # Create serial manager once
        self._serial_manager = SerialManager()
        
        # Create Trajectory Follower
        # self._trajectory_follower = TrajectoryFollower()
        
        # Create PID Controller
        self._pid_controller = [SimplePID(), SimplePID()]
        
    
    def update_position(self):
        pos = self._serial_manager.get_pos()

        # Calculate encoder changes
        left_enc_change = pos[1] - self.lastPos[1]
        right_enc_change = pos[0] - self.lastPos[0]
        
        # Update last positions
        self.lastPos[0] = pos[0]
        self.lastPos[1] = pos[1]

        # Calculate distances and angles
        left_distance = pos[1] / self.pulsesPerMM
        right_distance = pos[0] / self.pulsesPerMM
        distance = (left_distance + right_distance) / 2
        d_theta = (right_distance - left_distance) / self.wheelDistance

        # Update position and orientation
        self.extrax = distance * math.cos(self.theta + d_theta)
        self.extray = distance * math.sin(self.theta + d_theta)
        self.extraTheta = d_theta
        
        # Normalize angle to [-2π, 2π]
        while self.extraTheta > 2 * math.pi:
            self.extraTheta -= 2 * math.pi
        while self.extraTheta < -2 * math.pi:
            self.extraTheta += 2 * math.pi
        
        self.x += self.extrax
        self.y += self.extray
        
        self.extrax = 0
        self.extray = 0
        
        self.theta += self.extraTheta
        
        while(self.theta > 2 * math.pi):
            self.theta -= 2 * math.pi
        
        while(self.theta < -2 * math.pi):
            self.theta += 2 * math.pi   
            
        self.extraTheta = 0

        # Check if target is reached
        max_d = abs(self.target[0] - pos[0])
        max_d = max(max_d, abs(self.target[1] - pos[1]))

        if ((abs(left_enc_change) < self.pulsesCutoff and
             abs(right_enc_change) < self.pulsesCutoff and max_d < 30)):
            
            self.isDriving = False
            
            self.target[0] = pos[0]
            self.target[1] = pos[1]
        else:
            self.isDriving = True
            
    def reset_position(self):
        self.update_position()
        
        self.lastPos[0] = 0
        self.lastPos[1] = 0
        self._serial_manager.reset_pos()
        self.target[0] = 0
        self.target[1] = 0
    
    
    def drive_distance(self, distance: int):
        self.target[0:1] += self.pulsesValue * distance
        
    def turn_angle(self, degree: int):
        pulses_distance = self.wheelDistance * self.pulsesValue * math.pi * degree / 360
        self.target[0] += -pulses_distance
        self.target[1] += pulses_distance
    
    def pwm_process(self):
        self.target[0] = 0
        self.target[1] = 0
        
        prev_t = time.time_ns() // 1000
        last_pos_update = time.time_ns() // 1000

        while True:
            try:
                # time difference
                curr_t = time.time_ns() // 1000  # Get microseconds
                delta_t = float(curr_t - prev_t) / 1.0e6  # Convert to seconds
                prev_t = curr_t

                pos = self._serial_manager.get_pos()
                    
                if curr_t - last_pos_update >= 50000:
                    self.update_position()
                    last_pos_update = time.time_ns() // 1000
                
                scaled_factor = [0.0, 0.0]
                
                # Update last_pwm if not stopped
                if not self.stopped:
                    self.last_pwm = self.last_pwm + 1
                    self.last_pwm = min(self.current_pwm, max(self.pwm_cutoff, self.last_pwm))
                
                # Loop through motors
                for k in range(self.NMOTORS):
                    # Evaluate control signal
                    self.pid[k].evaluate(
                        pos[k], 
                        pos[not k],
                        self.target[k], 
                        self.target[not k],
                        delta_t
                    )
                    
                    scaled_factor[k] = float(self.pwm[k]) / self.last_pwm
                
                # Find max scaling factor and adjust PWM values
                max_factor = max(self.scaled_factor[0], self.scaled_factor[1])
                if max_factor > 1:
                    self.pwm[0] /= max_factor
                    self.pwm[1] /= max_factor
                
                if self.stopped:
                    # Decelerate for enemy
                    while self.last_pwm >= self.pwm_cutoff:
                        self.last_pwm -= 2
                        self._serial_manager.send_pwm([self.last_pwm, self.last_pwm], self.dir)
                        time.sleep(0.003)
                    
                    # Reset motors
                    self.dir = [0] * self.NMOTORS
                    self.pwm = [0] * self.NMOTORS
                
                self._serial_manager.send_pwm(self.pwm, self.dir)
                
                self.last_pwm = max(self.pwm[0], self.pwm[1])
                    
            
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