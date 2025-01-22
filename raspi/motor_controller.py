import math
import time

from data import SerialManager
from simple_pid import SimplePID

class MotorController():
    def __init__(self, serial_manager: SerialManager) -> None:
        self.serial_manager = serial_manager
        
        self.pwm = [0, 0]
        self.dir = [0, 0]
        
        self.pos = [0, 0]
        
        self.NMOTORS = 2
        self.pwmCutoff = 12 # Set minimum drivable pwm value
        self.pulsesCutoff = 4
        self.pwmMax = 254
        self.currentPwm = 254
        self.lastpwm = 0
        self.lastPos = [0, 0]
        self.target = [0, 0]

        self.pulsesPerEncRev = 1200
        self.encWheelDiameterCM = 4.975
        self.motorWheelDiameterCM = 7
        self.encWheelScope = self.encWheelDiameterCM * math.pi
        self.motorWheelScope = self.motorWheelDiameterCM * math.pi   # distance travelled per rev
        self.pulsesPerRev = self.pulsesPerEncRev * (self.motorWheelScope / self.encWheelScope)
        self.pulsesPerMM = self.pulsesPerRev / self.motorWheelScope / 10
        self.pulsesPerCM = self.pulsesPerRev / self.motorWheelScope
        self.pwmSpeed = 100                         # default pwm speed
        self.pulsesPerSec = self.pulsesPerRev       # goal pulses per sec 1680, 1 round per second
        self.wheelDistance = 130.53                  # abstand der encoderräder in mm, muss vllt geändert werden
        self.wheelDistanceBig = 204                 # in mm, muss vllt geändert werden

        self.pulsesValue = self.pulsesPerMM
        
        self.stopped = False
        
        self.prev_t = time.time_ns() // 1000
        self.last_pos_update = time.time_ns() // 1000
        self.scaled_factor = [0.0, 0.0]
        
        self.pid = [SimplePID(), SimplePID()]
    
    def update_position(self) -> bool:
        pos = self.serial_manager.get_pos()
        
        # set new x, y, theta
        self.x = pos[2]
        self.y = pos[3]
        self.theta = pos[4]

        # Calculate encoder changes
        left_enc_change = pos[1] - self.lastPos[1]
        right_enc_change = pos[0] - self.lastPos[0]
        
        # Update last positions
        self.lastPos[0] = pos[0]
        self.lastPos[1] = pos[1]

        # Check if target is reached
        max_d = abs(self.target[0] - pos[0])
        max_d = max(max_d, abs(self.target[1] - pos[1]))

        if ((abs(left_enc_change) < self.pulsesCutoff and
             abs(right_enc_change) < self.pulsesCutoff and max_d < 30)):
                        
            self.target[0] = pos[0]
            self.target[1] = pos[1]
            
            self.serial_manager.send_pwm([0, 0], [0, 0])

            return True

            
    def reset_position(self) -> None:
        self.update_position()
        self.serial_manager.reset_pos()
        
        self.lastPos[0] = 0
        self.lastPos[1] = 0
        self.target[0] = 0
        self.target[1] = 0
    
    def drive_distance(self, distance: int) -> None:
        self.reset_position()
        
        self.target[0] += self.pulsesValue * distance
        self.target[1] += self.pulsesValue * distance
        
    def turn_angle(self, degree: int) -> None:
        self.reset_position()
        
        pulses_distance = self.wheelDistance * self.pulsesValue * math.pi * degree / 360
        self.target[0] += -pulses_distance
        self.target[1] += pulses_distance
        
    def pwm_process(self):
        prev_t = time.time_ns() // 1000
        last_pos_update = time.time_ns() // 1000
        scaled_factor = [0.0, 0.0]

        while True:
            # time difference
            curr_t = time.time_ns() // 1000  # Get microseconds
            delta_t = float(curr_t - prev_t) / 1.0e6  # Convert to seconds
            prev_t = curr_t

            pos = self.serial_manager.get_pos()
                
            if curr_t - last_pos_update >= 50000:
                if self.update_position(): break
                last_pos_update = time.time_ns() // 1000
            
            
            # Update last_pwm if not stopped
            if not self.stopped:
                self.lastpwm = self.lastpwm + 1
                self.lastpwm = min(self.currentPwm, max(self.pwmCutoff, self.lastpwm))

            
            # Loop through motors
            for k in range(self.NMOTORS):
                # Evaluate control signal
                self.pwm[k], self.dir[k] = self.pid[k].evaluate(
                    pos[k], 
                    pos[not k],
                    self.target[k], 
                    self.target[not k],
                    delta_t
                )
                
                scaled_factor[k] = float(self.pwm[k]) / self.lastpwm
            
            # Find max scaling factor and adjust PWM values
            max_factor = max(scaled_factor[0], scaled_factor[1])
            if max_factor > 1:
                self.pwm[0] /= max_factor
                self.pwm[1] /= max_factor
            
            if self.stopped:
                # Decelerate for enemy
                while self.lastpwm >= self.pwm_cutoff:
                    self.lastpwm -= 2
                    self.serial_manager.send_pwm([self.lastpwm, self.lastpwm], self.dir)
                    time.sleep(0.003)
                
                # Reset motors
                for k in self.NMOTORS:
                    self.dir[k] = 0
                    self.pwm[k] = 0
            
            print(self.pwm)
            self.serial_manager.send_pwm(self.pwm, self.dir)
            
            self.lastpwm = max(self.pwm[0], self.pwm[1])