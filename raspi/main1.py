from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
import math
import threading
import time
from data import SerialManager
from trajectory_follower import TrajectoryFollower
from simple_pid import SimplePID

@dataclass
class Waypoint:
    x: float  # mm
    y: float  # mm
    theta: float = None  # radians, optional

class PathFollower:
    def __init__(self, look_ahead_distance: float = 100.0):
        self.look_ahead_distance = look_ahead_distance  # mm
        self.position_tolerance = 20.0  # mm
        self.angle_tolerance = math.radians(5)  # radians
        self.waypoints: List[Waypoint] = []
        self.current_waypoint_index = 0
        
    def add_waypoint(self, x: float, y: float, theta: float = None):
        """Add a waypoint to the path"""
        self.waypoints.append(Waypoint(x, y, theta))
    
    def set_path(self, waypoints: List[Tuple[float, float, float]]):
        """Set multiple waypoints at once"""
        self.waypoints = [Waypoint(x, y, theta) for x, y, theta in waypoints]
        self.current_waypoint_index = 0
    
    def get_next_movement(self, current_x: float, current_y: float, current_theta: float) -> Tuple[float, float]:
        """
        Calculate the next movement needed to follow the path
        Returns: (distance_to_drive, angle_to_turn)
        """
        if self.current_waypoint_index >= len(self.waypoints):
            return 0, 0
            
        target = self.waypoints[self.current_waypoint_index]
        
        # Calculate distance and angle to waypoint
        dx = target.x - current_x
        dy = target.y - current_y
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Calculate desired heading
        desired_theta = math.atan2(dy, dx)
        
        # Calculate angle difference
        angle_diff = math.atan2(math.sin(desired_theta - current_theta),
                              math.cos(desired_theta - current_theta))
        
        # Check if we reached the waypoint
        if distance < self.position_tolerance:
            if target.theta is not None:
                # If waypoint has specific orientation, turn to it
                final_angle_diff = math.atan2(math.sin(target.theta - current_theta),
                                            math.cos(target.theta - current_theta))
                if abs(final_angle_diff) > self.angle_tolerance:
                    return 0, math.degrees(final_angle_diff)
            
            # Move to next waypoint
            self.current_waypoint_index += 1
            return 0, 0
            
        # If angle difference is significant, turn first
        if abs(angle_diff) > self.angle_tolerance:
            return 0, math.degrees(angle_diff)
        
        # Otherwise, drive forward
        return min(distance, self.look_ahead_distance), 0
    
    def is_path_complete(self) -> bool:
        """Check if all waypoints have been reached"""
        return self.current_waypoint_index >= len(self.waypoints)

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
        self.pid = [SimplePID(), SimplePID()]

        self.path_follower = PathFollower()
        
    def follow_path(self):
        """Execute movement to follow the defined path"""
        print("Starting path following...")

        print(self.x)
        print(self.y)
        print(self.theta)
        
        while not self.path_follower.is_path_complete():
            # Get next movement command
            distance, angle = self.path_follower.get_next_movement(
                self.x, self.y, self.theta
            )

            print(self.x)
            print(self.y)
            print(self.theta)
            print(distance)
            print(angle)
            
            # Execute turn if needed
            if abs(angle) > 0:
                self.turn_angle(int(angle))
                self.pwm_process()
            
            # Execute forward movement if needed
            if abs(distance) > 0:
                self.drive_distance(int(distance))
                self.pwm_process()
            
            # Small delay to allow position update
            time.sleep(0.1)
        
        print("Path following complete!")
    
    def run_path_example(self):
        """Example of running a complex path"""
        # Define waypoints for a square path
        square_path = [
            (0, 0, 0),         # Start
            (1000, 0, None),   # Forward 1m
        ]
        
        # Set the path
        self.path_follower.set_path(square_path)
        
        # Execute the path
        self.follow_path()
    
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
        print(self.x)
        print(self.y)

        self.extrax = 0
        self.extray = 0
        
        self.theta += self.extraTheta
        print(self.theta)
        
        while(self.theta > 2 * math.pi):
            self.theta -= 2 * math.pi
        
        while(self.theta < -2 * math.pi):
            self.theta += 2 * math.pi   
            
        self.extraTheta = 0

        # # Check if target is reached
        # max_d = abs(self.target[0] - pos[0])
        # max_d = max(max_d, abs(self.target[1] - pos[1]))

        # if ((abs(left_enc_change) < self.pulsesCutoff and
        #      abs(right_enc_change) < self.pulsesCutoff and max_d < 30)):
            
        #     self.isDriving = False
            
        #     self.target[0] = pos[0]
        #     self.target[1] = pos[1]
        # else:
        #     self.isDriving = True
            
    def reset_position(self):
        self.update_position()
        
        self.lastPos[0] = 0
        self.lastPos[1] = 0
        self._serial_manager.reset_pos()
        self.target[0] = 0
        self.target[1] = 0
    
    
    def drive_distance(self, distance: int):
        self.target[0] += self.pulsesValue * distance
        self.target[1] += self.pulsesValue * distance
        
    def turn_angle(self, degree: int):
        pulses_distance = self.wheelDistance * self.pulsesValue * math.pi * degree / 360
        self.target[0] += -pulses_distance
        self.target[1] += pulses_distance
    
    def pwm_process(self):
        
        prev_t = time.time_ns() // 1000
        last_pos_update = time.time_ns() // 1000

        while True:
            try:
                # time difference
                curr_t = time.time_ns() // 1000  # Get microseconds
                delta_t = float(curr_t - prev_t) / 1.0e6  # Convert to seconds
                prev_t = curr_t

                #self.update_position()

                pos = self._serial_manager.get_pos()
                    
                if curr_t - last_pos_update >= 50000:
                    self.update_position()
                    last_pos_update = time.time_ns() // 1000
                
                scaled_factor = [0.0, 0.0]
                
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
                
                if(self.pwm[0] < self.pwmCutoff and self.pwm[1] < self.pwmCutoff):
                    self.pwm[0] = 0
                    self.pwm[1] = 0
                    self._serial_manager.send_pwm(self.pwm, self.dir)
                    break

                # Find max scaling factor and adjust PWM values
                max_factor = max(scaled_factor[0], scaled_factor[1])
                if max_factor > 1:
                    self.pwm[0] /= max_factor
                    self.pwm[1] /= max_factor
                
                if self.stopped:
                    # Decelerate for enemy
                    while self.lastpwm >= self.pulsesCutoff:
                        self.lastpwm -= 2
                        self._serial_manager.send_pwm([self.lastpwm, self.lastpwm], self.dir)
                        time.sleep(0.003)
                    
                    # Reset motors
                    for k in self.NMOTORS:
                        self.dir[k] = 0
                        self.pwm[k] = 0
                
                print(self.pwm)
                self._serial_manager.send_pwm(self.pwm, self.dir)
                
                self.lastpwm = max(self.pwm[0], self.pwm[1])
                    
            
            except Exception as e:
                print(f"Error in PWM process: {e}") 
                break

def main():
    controller = RobotController()
    
    # Example: Create a path and follow it
    controller.path_follower.set_path([
        (500, 0, None),      # Forward 500mm
    ])
    
    controller.follow_path()

if __name__ == '__main__':
    main()