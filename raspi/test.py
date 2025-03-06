#!/usr/bin/env python3
import math
from rplidar import RPLidar

PORT_NAME = '/dev/tty.usbserial-0001'

def run():
    lidar = RPLidar(PORT_NAME)
    
    for measurements in lidar.iter_measures():
        new_scan, quality, angle, distance = measurements
        
        # point in relation to bot
        d_x = distance * math.sin(angle * math.pi / 180)
        d_y = distance * math.cos(angle * math.pi / 180)
        
        # point in arena
        arena_angle = (-angle) + 180
        arena_x = distance * math.cos(arena_angle * math.pi / 180) + 300
        arena_y = distance * math.sin(arena_angle * math.pi / 180) + 300
                
        if abs(d_x) <= 300 and d_y <= 250 and d_y > 0 and quality > 10 and distance > 1:
            print(f'Obstacle: x: {d_x}, y: {d_y}, angle: {angle}, distance: {distance}')
            pass

if __name__ == '__main__':
    run()