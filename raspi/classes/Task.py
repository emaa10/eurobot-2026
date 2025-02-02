from motor_controller import MotorController

class Task():
    def __init__(self, motor_controller: MotorController, actions: list[str] = []):
        self.motor_controller = motor_controller
        self.successor : None | Task = None
        self.actions = actions
    
    # Sets next action and returns current Task (self or next task if current task finished)
    def next_action(self):
        if len(self.actions) <= 0:
            return None if not self.successor else self.successor.next_action()
        
        action = self.actions.pop(0)
        prefix = action[0]
        value = int(action[1:])
        
        match prefix:
            case 'd':
                self.motor_controller.reset()
                self.motor_controller.drive_distance(value)
            case 't':
                self.motor_controller.reset()
                self.motor_controller.turn_angle(value)
                
        return self