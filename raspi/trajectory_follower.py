import math
import numpy as np
from position import Position

import math

class TrajectoryFollower:
    def __init__(self, wheel_radius, wheel_base, max_linear_velocity=1, max_angular_velocity=1.0, max_pwm=255, min_pwm=12):
        """
        Initialize the trajectory follower for a differential drive robot.
        
        :param wheel_radius: Radius of the wheels (meters)
        :param wheel_base: Distance between the wheels (meters)
        :param max_linear_velocity: Maximum linear velocity (m/s)
        :param max_angular_velocity: Maximum angular velocity (rad/s)
        :param max_pwm: Maximum PWM value (typical for 8-bit PWM)
        :param min_pwm: Minimum PWM value to start motor movement
        """
        # Convert millimeters to meters for internal calculations
        self.wheel_radius = wheel_radius                   
        self.wheel_base = wheel_base                       
        self.max_linear_velocity = max_linear_velocity   
        self.max_angular_velocity = max_angular_velocity    
        self.max_pwm = max_pwm
        self.min_pwm = min_pwm
    
    def _calculate_velocities(self, current_pos: Position, target_trajectory, lookahead_distance_mm=500):
        """
        Calculate control signals for trajectory following using the Pure Pursuit method.
        
        :param current_pos: Current robot pose [x, y, theta]
        :param target_trajectory: List of trajectory points [[x1,y1], [x2,y2], ...]
        :param lookahead_distance_mm: Distance ahead to look for path following (mm)
        :return: Linear and angular velocities [v, omega]
        """
        # Convert current position and trajectory to meters
        current_pos = [
            current_pos.x / 1000, 
            current_pos.y / 1000, 
            current_pos.theta
        ]
        target_trajectory = [
            [x / 1000, y / 1000] for x, y in target_trajectory
        ]
        lookahead_distance = lookahead_distance_mm / 1000
        
        # Find the lookahead point
        lookahead_point = self._find_lookahead_point(current_pos, target_trajectory, lookahead_distance)
        
        if lookahead_point is None:
            return [0, 0]  # No valid lookahead point, stop
        
        # Extract current position and orientation
        x, y, theta = current_pos
        
        # Calculate the heading to the lookahead point
        goal_x, goal_y = lookahead_point
        angle_to_goal = math.atan2(goal_y - y, goal_x - x)
        
        # Calculate the cross-track error (lateral distance from path)
        cross_track_error = self._calculate_cross_track_error(current_pos, target_trajectory)
        
        # Calculate steering angle (bearing error)
        steering_angle = angle_to_goal - theta
        
        # Normalize steering angle to [-pi, pi]
        steering_angle = math.atan2(math.sin(steering_angle), math.cos(steering_angle))
        
        # Proportional control for linear and angular velocities
        # Reduce linear velocity based on how much we need to turn
        Kp_linear = 0.5  # Linear velocity gain
        Kp_angular = 1.0  # Angular velocity gain
        Kp_cross_track = 0.5  # Cross-track error gain
        
        # Linear velocity (reduce when turning)
        linear_velocity = Kp_linear * self.max_linear_velocity * (1 - abs(steering_angle) / math.pi)
        
        # Angular velocity (proportional to steering angle and cross-track error)
        angular_velocity = (Kp_angular * steering_angle + 
                            Kp_cross_track * cross_track_error)
        
        # limit velocities
        linear_velocity = max(-self.max_linear_velocity, 
                               min(linear_velocity, self.max_linear_velocity))
        angular_velocity = max(-self.max_angular_velocity, 
                                min(angular_velocity, self.max_angular_velocity))
        
        return [linear_velocity, angular_velocity]
    
    def _find_lookahead_point(self, current_pos, trajectory, lookahead_distance):
        """
        Find the lookahead point on the trajectory.
        
        :param current_pos: Current robot pose [x, y, theta] in meters
        :param trajectory: List of trajectory points in meters
        :param lookahead_distance: Desired lookahead distance in meters
        :return: Lookahead point [x, y] or None
        """
        x, y, theta = current_pos[0], current_pos[1], current_pos[2]
        
        # Find the closest point on the trajectory
        closest_point = None
        min_distance = float('inf')
        for point in trajectory:
            dist = math.sqrt((point[0] - x)**2 + (point[1] - y)**2)
            if dist < min_distance:
                min_distance = dist
                closest_point = point
        
        # If no points or no point beyond lookahead, return last point
        if not trajectory:
            return None
        
        # Find the point at lookahead distance
        for i in range(len(trajectory) - 1):
            p1 = trajectory[i]
            p2 = trajectory[i + 1]
            
            # Calculate segment length
            seg_length = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            
            # Interpolate along the segment
            if seg_length > 0:
                t = lookahead_distance / seg_length
                if 0 <= t <= 1:
                    lookahead_x = p1[0] + t * (p2[0] - p1[0])
                    lookahead_y = p1[1] + t * (p2[1] - p1[1])
                    return [lookahead_x, lookahead_y]
        
        # If no point found, return the last point
        return trajectory[-1]
    
    def _calculate_cross_track_error(self, current_pos, trajectory):
        """
        Calculate the cross-track error (lateral distance from the path).
        
        :param current_pos: Current robot pose [x, y, theta] in meters
        :param trajectory: List of trajectory points in meters
        :return: Cross-track error in meters
        """
        x, y, _ = current_pos
        
        # If trajectory is too short, return 0
        if len(trajectory) < 2:
            return 0
        
        # Find the line segment closest to the current position
        min_distance = float('inf')
        for i in range(len(trajectory) - 1):
            p1 = trajectory[i]
            p2 = trajectory[i + 1]
            
            # Calculate cross-track error using point-to-line distance
            # Line segment from p1 to p2
            line_length_sq = (p2[0] - p1[0])**2 + (p2[1] - p1[1])**2
            
            if line_length_sq == 0:
                # If line segment is a point, calculate distance to that point
                dist = math.sqrt((x - p1[0])**2 + (y - p1[1])**2)
            else:
                # Project point onto line segment
                t = max(0, min(1, ((x - p1[0]) * (p2[0] - p1[0]) + 
                                   (y - p1[1]) * (p2[1] - p1[1])) / line_length_sq))
                
                # Closest point on the line segment
                proj_x = p1[0] + t * (p2[0] - p1[0])
                proj_y = p1[1] + t * (p2[1] - p1[1])
                
                # Calculate distance
                dist = math.sqrt((x - proj_x)**2 + (y - proj_y)**2)
            
            # Keep track of minimum distance
            min_distance = min(min_distance, dist)
        
        return min_distance
    
    def _velocities_to_pwm(self, linear_velocity, angular_velocity):
        """
        Convert linear and angular velocities to left and right wheel PWM values
        
        :param linear_velocity: Desired linear velocity (m/s)
        :param angular_velocity: Desired angular velocity (rad/s)
        :return: Tuple of (left_pwm, right_pwm)
        """
        
        # Kinematic model for differential drive robot
        # Calculate wheel velocities
        right_wheel_velocity = linear_velocity + (angular_velocity * self.wheel_base / 2)
        left_wheel_velocity = linear_velocity - (angular_velocity * self.wheel_base / 2)
        
        # Convert wheel velocities to PWM
        # This is a simplified linear mapping - real-world implementations 
        # will need more sophisticated calibration
        left_pwm = self._velocity_to_dual_motor_pwm(left_wheel_velocity)
        right_pwm = self._velocity_to_dual_motor_pwm(right_wheel_velocity)
        
        return [left_pwm, right_pwm]
    
    def _velocity_to_dual_motor_pwm(self, wheel_velocity):
        """
        Convert a single wheel velocity to dual PWM values
        
        :param wheel_velocity: Velocity of a single wheel (m/s)
        :return: Tuple of (l_pwm, r_pwm)
        """
        # Normalize velocity to [-1, 1] range
        normalized_velocity = wheel_velocity / self.max_linear_velocity
        
        # Map normalized velocity to PWM range with separate forward and reverse PWM
        if normalized_velocity > 0:
            # Positive direction
            l_pwm = int(normalized_velocity * (self.max_pwm - self.min_pwm) + self.min_pwm)
            r_pwm = 0
        elif normalized_velocity < 0:
            # Negative direction
            l_pwm = 0
            r_pwm = int(abs(normalized_velocity) * (self.max_pwm - self.min_pwm) + self.min_pwm)
        else:
            # Zero velocity
            l_pwm = 0
            r_pwm = 0
        
        # Ensure PWM values are within valid range
        l_pwm = max(min(l_pwm, self.max_pwm), 0)
        r_pwm = max(min(r_pwm, self.max_pwm), 0)
    
        return (l_pwm, r_pwm)
    
    def calibrate_velocity_to_pwm(self, test_velocities_mm_s):
        """
        Helper method to assist in calibrating velocity to PWM mapping
        
        :param test_velocities_mm_s: List of test velocities (mm/s) to map
        :return: Calibration data
        """
        calibration_data = []
        for velocity_mm_s in test_velocities_mm_s:
            velocity = velocity_mm_s
            pwm = self._velocity_to_single_motor_pwm(velocity)
            calibration_data.append({
                'velocity_mm_s': velocity_mm_s,
                'pwm': pwm
            })
        return calibration_data
    
    def calculate_pwm(self, current_pos, target_trajectory):
        """
        Calculate PWM values for following a trajectory
        
        :param current_pos: Current robot pose [x, y, theta]
        :param target_trajectory: List of trajectory points [[x1,y1], [x2,y2], ...]
        :return: PWM values for left and right motors
        """
        linear_velocity, angular_velocity = self._calculate_velocities(current_pos, target_trajectory)
        pwm_values = self._velocities_to_pwm(linear_velocity, angular_velocity)
        
        return pwm_values
    