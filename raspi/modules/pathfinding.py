from math import sqrt
import random
from time import time_ns
import numpy as np
import matplotlib.pyplot as plt
from position import Position

def time_ms():
    return time_ns() // 1000000

def add_with_limits(a, b, max_value):
    result = max(a + b, 0)
    return min(result, max_value)

class Pathfinder():
    def __init__(self, start=Position(400,1800), target=Position(2700, 1800), map_size=[3000, 2000], max_iters=1000, bot_width=180):
        self.start = start
        self.target = target
        self.map_size = map_size
        self.obstacle_map = np.zeros((map_size[1], map_size[0]), dtype='int32')
        self.max_iters = max_iters
        self.bot_width = bot_width
        
        # stacks
        self.add_stack(Position(900, 900), Position(1300, 1000))
        self.add_stack(Position(1700, 900), Position(2100, 1000))
        self.add_stack(Position(1950, 1700), Position(2350, 1800))
        self.add_stack(Position(650, 1700), Position(1050, 1800))
        self.add_stack(Position(550, 0), Position(950, 100))
        self.add_stack(Position(2050, 0), Position(2450, 100))
        self.add_stack(Position(2600, 450), Position(2999, 550))
        self.add_stack(Position(0, 450), Position(400, 550))
        self.add_stack(Position(2600, 1000), Position(2999, 1100))
        self.add_stack(Position(0, 1000), Position(400, 1100))
        
        # stage and ramp
        self.add_obstacle(Position(650, 1800), Position(2350, 1999))
        self.add_obstacle(Position(1050, 1500), Position(1950, 1800))
        
        # simas
        self.add_obstacle(Position(0, 1550), Position(150, 1999))
        self.add_obstacle(Position(2850, 1550), Position(2999, 1999))
    
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
    
    def plan(self, start, target) -> list[Position]:       
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
            print("No path found")
            return []
        
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
    
    def proccess(self, display: bool = False) -> None:
        time_start = time_ms()
        path = self.plan(self.start, self.target)
        print(f'{int(time_ms() - time_start)} ms')
        if display: self.display(path)
        
if __name__ == "__main__":
    pathfinder = Pathfinder(target=Position(2800, 750))
    pathfinder.proccess(True)
