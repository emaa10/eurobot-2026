from Task import Task

class CollectStage1(Task):
    def __init__(self, motor_controller):
        super().__init__(motor_controller)
        self.actions = ['x90y90t29']