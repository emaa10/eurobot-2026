from typing import Self

from motor_controller import MotorController

class Task():
    def __init__(self, motor_controller: MotorController, actions: list[str] = [], successor: Self | None = None):
        self.motor_controller = motor_controller
        self.actions = actions
        self.successor = successor
        
    def add_task(self, task: Self) -> Self:
        if not self.successor:
            self.successor = task
            return

        self.successor.add_task(task)
        
    # Sets next action and returns current Task (self or next task if current task finished)
    def next_action(self) -> Self:
        if len(self.actions) <= 0:
            if not self.successor: return None
            
            self.successor.next_action()
            return self.successor 
        
        action = self.actions.pop(0)
        prefix = action[0]
        value = action[1:]
        
        match prefix:
            case 'd':
                self.motor_controller.drive_distance(int(value))
            case 't':
                self.motor_controller.turn_angle(float(value))
            case 'r':
                self.motor_controller.turn_to(int(value))
            case 'p':
                x, y, theta = value.split(';')
                actions = self.motor_controller.drive_to(int(x), int(y), int(theta))
                actions.extend(self.actions)
                print(actions)
                self.actions = actions
                print(self.actions)
                return self.next_action()
                
        return self