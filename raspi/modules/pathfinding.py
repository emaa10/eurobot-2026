from time import time_ns
from math import sqrt
import matplotlib.pyplot as plt
import numpy as np
import random
import logging

from position import Position

def time_ms():
    return time_ns() // 1000000

def add_with_limits(a, b, max_value):
    result = max(a + b, 0)
    return min(result, max_value)

class Pathfinder():
    def __init__(self, start=Position(40,180), target=Position(270, 180), map_size=[300, 200], max_iters=1000, bot_width=17):
        self.start = start
        self.target = target
        self.map_size = map_size
        self.obstacle_map = np.zeros((map_size[1], map_size[0]), dtype='int32')
        self.max_iters = max_iters
        self.bot_width = bot_width
        
        # stacks
        self.add_stack(Position(90, 90), Position(130, 100))
        self.add_stack(Position(170, 90), Position(210, 100))
        self.add_stack(Position(195, 170), Position(235, 180))
        self.add_stack(Position(65, 170), Position(105, 180))
        self.add_stack(Position(55, 0), Position(95, 10))
        self.add_stack(Position(205, 0), Position(245, 10))
        self.add_stack(Position(260, 45), Position(299, 55))
        self.add_stack(Position(0, 45), Position(40, 55))
        self.add_stack(Position(260, 100), Position(299, 110))
        self.add_stack(Position(0, 100), Position(40, 110))
        
        # stage and ramp
        self.add_obstacle(Position(65, 180), Position(235, 199))
        self.add_obstacle(Position(105, 150), Position(195, 180))
        
        # simas
        self.add_obstacle(Position(0, 155), Position(15, 199))
        self.add_obstacle(Position(285, 155), Position(299, 199))
        
        # middle_points
        self.middle_points = [Position(150, 75), Position(150, 115), Position(75, 50), Position(225, 50)]
        
        self.logger = logging.getLogger(__name__)
    
    def add_stack(self, pos1: Position, pos2: Position) -> None:
        self.obstacle_map[pos1.y:pos2.y, pos1.x:pos2.x] = 2
        
    def add_obstacle(self, pos1: Position, pos2: Position) -> None:
        self.obstacle_map[pos1.y:pos2.y, pos1.x:pos2.x] = 1
        
    def set_start_target(self, start: Position, target: Position) -> None:
        self.start = start
        self.target = target
        
    def distance(self, node1: Position, node2: Position) -> int:
        return int(sqrt((node1.x - node2.x)**2+(node1.y - node2.y)**2))
    
    def calculate_parallel_points(self, pos1: Position, pos2: Position, distance) -> list[Position]:
        point1 = np.array([pos1.x, pos1.y])
        point2 = np.array([pos2.x, pos2.y])
        
        d = point2 - point1
        n = np.array([-d[1], d[0]])
        unit_n = n / np.linalg.norm(n)
        shift_vector = distance * unit_n
        
        point1 = point1 + shift_vector
        point2 = point2 + shift_vector
        
        # Ensure points are within map bounds
        point1[0] = np.clip(point1[0], 0, self.map_size[0]-1)
        point1[1] = np.clip(point1[1], 0, self.map_size[1]-1)
        point2[0] = np.clip(point2[0], 0, self.map_size[0]-1)
        point2[1] = np.clip(point2[1], 0, self.map_size[1]-1)
        
        return Position(int(point1[0]), int(point1[1])), Position(int(point2[0]), int(point2[1]))
    
    def is_point_valid(self, x: int, y: int) -> bool:
        return 0 <= x < self.map_size[0] and 0 <= y < self.map_size[1]

    def collission(self, node1: Position, node2: Position) -> bool:
        distance = self.distance(node1, node2)
        if distance == 0:
            return False
        
        # Check points along the path
        steps = max(distance * 2, 1)  # Increase sampling to avoid missing obstacles
        for i in range(steps):
            t = i / steps
            x = int(node1.x + t * (node2.x - node1.x))
            y = int(node1.y + t * (node2.y - node1.y))
            
            # Check if point is within map bounds
            if not self.is_point_valid(x, y):
                return True
                        
            if self.obstacle_map[y, x] != 0:
                return True
            
        return False
    
    def collission_with_bot(self, node1: Position, node2: Position) -> bool:
        # Check if start and end points are valid
        if not (self.is_point_valid(node1.x, node1.y) and self.is_point_valid(node2.x, node2.y)):
            return True
        
        # Check central path
        if self.collission(node1, node2):
            return True
            
        # Check robot width boundaries
        right1, right2 = self.calculate_parallel_points(node1, node2, self.bot_width)
        left1, left2 = self.calculate_parallel_points(node1, node2, -self.bot_width)
        
        return self.collission(right1, right2) or self.collission(left1, left2)
    
    def plan(self, start, target) -> list[Position] | None:
        # if no collision return target         
        if not self.collission_with_bot(start, target):
            return [target]
        
        # look for possible paths
        possibilities = []
        for i in range(self.max_iters):
            pos = Position(random.randint(0, self.map_size[0]-1), 
                         random.randint(0, self.map_size[1]-1))
            if not self.collission_with_bot(start, pos) and not self.collission_with_bot(pos, target):
                possibilities.append(pos)
        
        # check if paths were found
        if len(possibilities) <= 0:
            self.logger.info("No path found")
            return None
        
        self.logger.info("path found")
        
        # find best pos (shortest path)
        best_pos_index = 0
        best_pos_distance = float('inf')
        for i, pos in enumerate(possibilities):
            dist = self.distance(start, pos) + self.distance(pos, target)
            if dist < best_pos_distance:
                best_pos_index = i
                best_pos_distance = dist
            
        return [possibilities[best_pos_index], target]
    
    def display(self, path: list[Position]):
        plt.imshow(self.obstacle_map, cmap='gray', origin='lower')
        
        if path is not None:
            x = [self.start.x] 
            y = [self.start.y]
            for i in path: 
                x.append(i.x)
                y.append(i.y)
            x.append(self.target.x)
            y.append(self.target.y)
            
            plt.plot(x, y, '-r', linewidth=2, label='Path')
            
            for i in path:
                plt.plot(i.x, i.y, 'bo', label='Step')
        else: 
            plt.plot([self.target.x, self.start.x], [self.target.y, self.start.y], '-r', linewidth=2, label='Path')
    
        plt.plot(self.start.x, self.start.y, 'go', label='Start')
        plt.plot(self.target.x, self.target.y, 'ro', label='Target')

        plt.xlim(0, self.map_size[0])
        plt.ylim(0, self.map_size[1])
        plt.legend()
        plt.grid(True)
        plt.show()
        
    def find_alternative(self):
        middle_point_x = self.target.x - self.start.x
        middle_point_y = self.target.y - self.start.y
        
        def distance_to_middle(p: Position):
            return self.distance(p, Position(middle_point_x, middle_point_y))
        
        sorted_middle_points = sorted(self.middle_points, key=distance_to_middle)
        
        for point in sorted_middle_points:
            path1 = self.plan(self.start, point)
            path2 = self.plan(point, self.target)
            if path1 and path2:
                path1 += path2
                return path1 
        
        return None
    
    def proccess(self, start: Position, target: Position, debug = False) -> list[Position]:
        
        self.start = start
        self.target = target
        
        if debug: time_start = time_ms()
        path = self.plan(self.start, self.target)
        
        if not path:
            path = self.find_alternative()
        
        if debug: self.logger.info(f'{int(time_ms() - time_start)} ms')
        if debug: self.display(path)
        
        return path
        
if __name__ == "__main__":
    pathfinder = Pathfinder(start=Position(25, 10), target=Position(30, 135))
    pathfinder.proccess(Position(25, 10), Position(20, 80), True)
