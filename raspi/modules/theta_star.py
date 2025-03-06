import heapq
import math
import matplotlib.pyplot as plt
import numpy as np
from time import time_ns

class Node:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.g_cost = float('inf')  # Cost from start to this node
        self.h_cost = 0  # Heuristic cost (estimated cost to goal)
        self.f_cost = float('inf')  # g_cost + h_cost
        self.parent = None
        
        
    def __lt__(self, other):
        # For priority queue comparison
        return self.f_cost < other.f_cost
    
    def __eq__(self, other):
        if other is None:
            return False
        return self.x == other.x and self.y == other.y
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def position(self):
        return (self.x, self.y)

class ThetaStar:
    def __init__(self, grid_size):
        self.grid = np.zeros((grid_size[0], grid_size[1]))
        
        # Initialize obstacles
        self.init_obstacles()
        
    def init_obstacles(self):
        # stacks
        self.add_stack((900, 900), (1300, 1000))
        self.add_stack((1700, 900), (2100, 1000))
        self.add_stack((1950, 1700), (2350, 1800))
        self.add_stack((650, 1700), (1050, 1800))
        self.add_stack((550, 0), (950, 100))
        self.add_stack((2050, 0), (2450, 100))
        self.add_stack((2600, 450), (2999, 550))
        self.add_stack((0, 450), (400, 550))
        self.add_stack((2600, 1000), (2999, 1100))
        self.add_stack((0, 1000), (400, 1100))
        
        # stage and ramp
        self.add_obstacle((650, 1800), (2350, 1999))
        self.add_obstacle((1050, 1500), (1950, 1800))
        
        # simas
        self.add_obstacle((0, 1550), (150, 1999))
        self.add_obstacle((2850, 1550), (2999, 1999))

    def euclidean_distance(self, a, b):
        return math.sqrt((a.x - b.x)**2 + (a.y - b.y)**2)
    
    def add_stack(self, pos1, pos2) -> None:
        x1 = int(pos1[0]/10)
        x2 = int(pos2[0]/10)
        y1 = int(pos1[1]/10)
        y2 = int(pos2[1]/10)
        self.grid[y1:y2, x1:x2] = 2
        
    def add_obstacle(self, pos1, pos2) -> None:
        x1 = int(pos1[0]/10)
        x2 = int(pos2[0]/10)
        y1 = int(pos1[1]/10)
        y2 = int(pos2[1]/10)
        self.grid[y1:y2, x1:x2] = 1

    def line_of_sight(self, a, b):
        """Check if there's a clear line of sight between two nodes"""
        x0, y0 = int(a.x), int(a.y)
        x1, y1 = int(b.x), int(b.y)
        
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        while x0 != x1 or y0 != y1:
            if x0 < 0 or y0 < 0 or x0 >= len(self.grid[0]) or y0 >= len(self.grid) or self.grid[y0][x0] >= 1:
                return False  # Obstacle found
            
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
                
        return True

    def calculate_turn_penalty(self, parent, current, neighbor):
        """Calculate turn penalty based on angle change"""
        if parent is None:
            return 0
        
        # Calculate vectors
        v1 = (current.x - parent.x, current.y - parent.y)
        v2 = (neighbor.x - current.x, neighbor.y - current.y)
        
        # Normalize vectors
        v1_mag = math.sqrt(v1[0]**2 + v1[1]**2)
        v2_mag = math.sqrt(v2[0]**2 + v2[1]**2)
        
        if v1_mag == 0 or v2_mag == 0:
            return 0
        
        v1_norm = (v1[0]/v1_mag, v1[1]/v1_mag)
        v2_norm = (v2[0]/v2_mag, v2[1]/v2_mag)
        
        # Calculate dot product
        dot_product = v1_norm[0]*v2_norm[0] + v1_norm[1]*v2_norm[1]
        dot_product = max(-1, min(1, dot_product))  # Clamp to [-1, 1]
        
        # Calculate angle (in radians)
        angle = math.acos(dot_product)
        
        # Convert to degrees and apply penalty (adjust multiplier as needed)
        turn_penalty = 2.0 * math.degrees(angle)
        
        return turn_penalty

    def get_neighbors(self, node, diagonals=True):
        """Get valid neighbors for a node"""
        neighbors = []
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # 4-connectivity
        
        if diagonals:
            directions += [(1, 1), (1, -1), (-1, 1), (-1, -1)]  # 8-connectivity
        
        for dx, dy in directions:
            new_x, new_y = node.x + dx, node.y + dy
            
            # Check if within grid bounds
            if 0 <= new_x < len(self.grid[0]) and 0 <= new_y < len(self.grid):
                # Check if not an obstacle
                if self.grid[int(new_y)][int(new_x)] == 0:
                    neighbors.append(Node(new_x, new_y))
                    
        return neighbors

    def theta_star(self, start, goal, turn_penalty_weight=2.0):
        """Implementation of Theta* algorithm"""
        open_set = []
        closed_set = set()
        
        start_node = Node(start[0], start[1])
        goal_node = Node(goal[0], goal[1])
        
        start_node.g_cost = 0
        start_node.h_cost = self.euclidean_distance(start_node, goal_node)
        start_node.f_cost = start_node.h_cost
        
        heapq.heappush(open_set, start_node)
        node_dict = {start_node.position(): start_node}
        
        while open_set:
            current = heapq.heappop(open_set)
            
            if current.position() == goal_node.position():
                # Reconstruct path
                path = []
                while current:
                    path.append((current.x, current.y))
                    current = current.parent
                return path[::-1]  # Reverse to get start-to-goal path
            
            closed_set.add(current.position())
            
            for neighbor in self.get_neighbors(current):
                if neighbor.position() in closed_set:
                    continue
                
                in_open_set = False
                for i, node in enumerate(open_set):
                    if node.position() == neighbor.position():
                        neighbor = node
                        in_open_set = True
                        break
                
                # Theta* Path-1: Try to connect parent to neighbor if line of sight exists
                if current.parent and self.line_of_sight(current.parent, neighbor):
                    # Calculate new g_cost through parent
                    turn_penalty = self.calculate_turn_penalty(
                        current.parent.parent, current.parent, neighbor
                    ) * turn_penalty_weight if current.parent.parent else 0
                    
                    new_g_cost = current.parent.g_cost + self.euclidean_distance(current.parent, neighbor) + turn_penalty
                    
                    if new_g_cost < neighbor.g_cost:
                        neighbor.g_cost = new_g_cost
                        neighbor.parent = current.parent
                        neighbor.h_cost = self.euclidean_distance(neighbor, goal_node)
                        neighbor.f_cost = neighbor.g_cost + neighbor.h_cost
                        
                        if not in_open_set:
                            heapq.heappush(open_set, neighbor)
                            node_dict[neighbor.position()] = neighbor
                        # If in open_set, it will be reordered automatically in next pop
                
                # Theta* Path-2: Connect through current node
                else:
                    turn_penalty = self.calculate_turn_penalty(
                        current.parent, current, neighbor
                    ) * turn_penalty_weight if current.parent else 0
                    
                    new_g_cost = current.g_cost + self.euclidean_distance(current, neighbor) + turn_penalty
                    
                    if new_g_cost < neighbor.g_cost:
                        neighbor.g_cost = new_g_cost
                        neighbor.parent = current
                        neighbor.h_cost = self.euclidean_distance(neighbor, goal_node)
                        neighbor.f_cost = neighbor.g_cost + neighbor.h_cost
                        
                        if not in_open_set:
                            heapq.heappush(open_set, neighbor)
                            node_dict[neighbor.position()] = neighbor
                        # If in open_set, it will be reordered automatically in next pop
        
        return None  # No path found

    def post_process_path(self, path):
        """Reduce unnecessary waypoints while maintaining line of sight"""
        if not path or len(path) < 3:
            return path
        
        result = [path[0]]
        current_point = 0
        
        while current_point < len(path) - 1:
            # Try to find the furthest point that has line of sight
            for i in range(len(path) - 1, current_point, -1):
                start_node = Node(path[current_point][0], path[current_point][1])
                end_node = Node(path[i][0], path[i][1])
                
                if self.line_of_sight(start_node, end_node):
                    if i != current_point + 1:  # If we're skipping points
                        result.append(path[i])
                    current_point = i
                    break
            else:
                # If no point with line of sight found, add the next point
                current_point += 1
                if current_point < len(path):
                    result.append(path[current_point])
        
        return result

    def visualize_path(self, path, start, goal):
        """Visualize the grid, obstacles, and found path"""
        fig, ax = plt.subplots(figsize=(10, 10))
        
        plt.imshow(self.grid, cmap='gray', origin='lower')
        
        path_x = [p[0] for p in path]
        path_y = [p[1] for p in path]
        print(path_x)
        print(path_y)
        plt.plot(path_x, path_y, 'b-', linewidth=2)
        plt.plot(path_x, path_y, 'ro', markersize=5)
        
        # Highlight start and goal
        plt.plot(start[0], start[1], 'go', markersize=10)
        plt.plot(goal[0], goal[1], 'mo', markersize=10)
        
        # Set limits and labels
        ax.set_xlim(-0.5, len(self.grid[0]) - 0.5)
        ax.set_ylim(-0.5, len(self.grid) - 0.5)
        ax.set_aspect('equal')
        ax.grid(True)
        plt.title("Theta* Path for Differential Drive Robot")
        
        # Show plot
        plt.show()

    def main(self, start, goal):    
        # Find path
        time_start = time_ns()
        path = self.theta_star(start, goal, turn_penalty_weight=2.0)
        time_end = time_ns()
        time_delta = (time_end - time_start) // 1000000
        print(time_delta)
        
        if path:
            print(f"Found path with {len(path)} waypoints:")
            for p in path:
                print(f"  ({p[0]}, {p[1]})")
            
            # # Post-process to remove unnecessary waypoints
            # smooth_path = self.post_process_path(path)
            # print(f"\nSmoothed path with {len(smooth_path)} waypoints:")
            # for p in smooth_path:
            #     print(f"  ({p[0]}, {p[1]})")
            
            # Visualize
            self.visualize_path(path, start, goal)
        else:
            print("No path found")

# Run the example
if __name__ == "__main__":
    theta_star = ThetaStar((200, 300))
    theta_star.main((40,180), (280, 40))