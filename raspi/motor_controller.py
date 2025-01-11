import math
import time

from data import SerialManager

class MotorController():
    def __init__(self, serial_manager: SerialManager):
        self.serial_manager = serial_manager
        
        self.pwm = [0, 0]
        self.dir = [0, 0]
        
        self.pos = [0, 0]
        
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
        
        self.prev_t = time.time_ns() // 1000
        self.last_pos_update = time.time_ns() // 1000
        self.scaled_factor = [0.0, 0.0]
    
    def update_position(self):
        # Calculate encoder changes
        left_enc_change = self.pos[1] - self.lastPos[1]
        right_enc_change = self.pos[0] - self.lastPos[0]
        
        # Update last positions
        self.lastPos[0] = self.pos[0]
        self.lastPos[1] = self.pos[1]

        # Check if target is reached
        max_d = abs(self.target[0] - self.pos[0])
        max_d = max(max_d, abs(self.target[1] - self.pos[1]))

        if ((abs(left_enc_change) < self.pulsesCutoff and
             abs(right_enc_change) < self.pulsesCutoff and max_d < 30)):
            
            self.isDriving = False
            
            self.target[0] = self.pos[0]
            self.target[1] = self.pos[1]
        else:
            self.isDriving = True
            
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
        
    def proccess_pwm(self, pos: list[int]) -> None:
        # time difference
        curr_t = time.time_ns() // 1000  # Get microseconds
        delta_t = float(curr_t - self.prev_t) / 1.0e6  # Convert to seconds
        self.prev_t = curr_t
            
        if curr_t - self.last_pos_update >= 50000:
            self.pos = pos
            self.update_position()
            self.last_pos_update = time.time_ns() // 1000
        
        
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
            
            self.scaled_factor[k] = float(self.pwm[k]) / self.lastpwm
        
        # Find max scaling factor and adjust PWM values
        max_factor = max(self.scaled_factor[0], self.scaled_factor[1])
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