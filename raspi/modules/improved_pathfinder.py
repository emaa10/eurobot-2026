from math import sqrt
from time import time_ns
import random
import numpy as np
import matplotlib.pyplot as plt
from position import Position

class Pathfinder():
    def __init__(self, start=Position(400,1800), target=Position(2500, 1250), map_size=[3000, 2000], max_iters=1250, bot_width=180):
        self.start = start
        self.target = target
        self.map_size = map_size
        self.obstacle_map = np.zeros((map_size[1], map_size[0]), dtype='int32')
        self.max_iters = max_iters
        self.bot_width = bot_width
        self.min_segment_length = bot_width * 2
        
        # Initialize obstacles
        self.init_obstacles()
        
    def init_obstacles(self):
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
        
    def distance(self, node1: Position, node2: Position) -> float:
        return sqrt((node1.x - node2.x)**2 + (node1.y - node2.y)**2)
    
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
        
        steps = max(int(distance * 2), 1)  # Increase sampling to avoid missing obstacles
        for i in range(steps):
            t = i / steps
            x = int(node1.x + t * (node2.x - node1.x))
            y = int(node1.y + t * (node2.y - node1.y))
            
            if not self.is_point_valid(x, y):
                return True
                        
            if self.obstacle_map[y, x] != 0:
                return True
            
        return False
    
    def collission_with_bot(self, node1: Position, node2: Position) -> bool:
        if not (self.is_point_valid(node1.x, node1.y) and self.is_point_valid(node2.x, node2.y)):
            return True
        
        if self.collission(node1, node2):
            return True
            
        right1, right2 = self.calculate_parallel_points(node1, node2, self.bot_width)
        left1, left2 = self.calculate_parallel_points(node1, node2, -self.bot_width)
        
        return self.collission(right1, right2) or self.collission(left1, left2)
    
    def generate_random_point(self, current: Position, target: Position, exploration_rate: float) -> Position:
        """Generate a random point with variable exploration vs exploitation."""
        if random.random() < exploration_rate:
            # Pure random (exploration)
            x = random.randint(0, self.map_size[0]-1)
            y = random.randint(0, self.map_size[1]-1)
        else:
            # Biased towards target (exploitation)
            bias = random.uniform(0.2, 0.8)
            noise = self.bot_width * 4  # Add some noise to avoid getting stuck
            
            x = int(current.x + (target.x - current.x) * bias + random.uniform(-noise, noise))
            y = int(current.y + (target.y - current.y) * bias + random.uniform(-noise, noise))
            
            x = np.clip(x, 0, self.map_size[0]-1)
            y = np.clip(y, 0, self.map_size[1]-1)
            
        return Position(x, y)

    def find_path_segment(self, start: Position, target: Position, attempt: int = 0) -> list[Position]:
        """Find a valid path segment with increasing exploration on repeated attempts."""
        if not self.collission_with_bot(start, target):
            return [target]

        # Increase exploration rate and number of points with each failed attempt
        exploration_rate = min(0.3 + (attempt * 0.1), 0.8)
        max_points = min(3 + attempt, 6)
        points_range = range(1, max_points + 1)
        
        best_points = []
        best_distance = float('inf')
        
        # Try different numbers of intermediate points
        for num_points in points_range:
            for _ in range(self.max_iters // len(points_range)):
                current_points = []
                current_pos = start
                valid_segment = True
                
                # Generate intermediate points
                for _ in range(num_points):
                    point = self.generate_random_point(current_pos, target, exploration_rate)
                    
                    if self.collission_with_bot(current_pos, point):
                        valid_segment = False
                        break
                    
                    current_points.append(point)
                    current_pos = point
                
                # Check final segment to target
                if valid_segment and not self.collission_with_bot(current_pos, target):
                    current_points.append(target)
                    
                    # Calculate total path distance
                    total_distance = self.distance(start, current_points[0])
                    for i in range(len(current_points)-1):
                        total_distance += self.distance(current_points[i], current_points[i+1])
                    
                    if total_distance < best_distance:
                        best_distance = total_distance
                        best_points = current_points.copy()
        
        return best_points

    def optimize_path(self, path: list[Position]) -> list[Position]:
        """Remove unnecessary waypoints while maintaining a valid path."""
        if len(path) <= 1:
            return path

        optimized = [path[0]]
        current_point = 0

        while current_point < len(path) - 1:
            # Try to connect to furthest possible point
            for i in range(len(path)-1, current_point, -1):
                if not self.collission_with_bot(path[current_point], path[i]):
                    optimized.append(path[i])
                    current_point = i
                    break
            if current_point == len(path) - 1:
                break

        return optimized

    def plan(self, start: Position, target: Position) -> list[Position]:
        """Try to find a path with multiple attempts, increasing exploration each time."""
        if not self.collission_with_bot(start, target):
            return [target]
        
        max_attempts = 5
        for attempt in range(max_attempts):
            path = self.find_path_segment(start, target, attempt)
            if path:
                return self.optimize_path(path)
            
            # If we failed, print status and try again with more exploration
            print(f"Attempt {attempt + 1} failed, trying with more exploration...")
        
        print("No path found after all attempts")
        return []
    
    def display(self, path: list[Position]):
        plt.figure(figsize=(12, 8))
        plt.imshow(self.obstacle_map, cmap='gray', origin='lower')
        
        if path is not None:
            x = [self.start.x] 
            y = [self.start.y]
            for i in path: 
                x.append(i.x)
                y.append(i.y)
            
            plt.plot(x, y, '-r', linewidth=2, label='Path')
            
            for i in path:
                plt.plot(i.x, i.y, 'bo', label='Waypoint')
    
        plt.plot(self.start.x, self.start.y, 'go', label='Start', markersize=10)
        plt.plot(self.target.x, self.target.y, 'ro', label='Target', markersize=10)

        plt.xlim(0, self.map_size[0])
        plt.ylim(0, self.map_size[1])
        plt.legend()
        plt.grid(True)
        plt.show()
        
    def proccess(self, display: bool = False) -> None:
        time_start = time_ns()
        path = self.plan(self.start, self.target)
        time_end = time_ns()
        time_delta = (time_end - time_start) // 1000000
        print(f'{time_delta} ms')
        if display: self.display(path)
        

if __name__ == "__main__":
    # Create pathfinder instance
    pathfinder = Pathfinder(target=Position(2800, 750))

    # Run pathfinding with visualization
    pathfinder.proccess(display=True)