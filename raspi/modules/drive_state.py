from modules.task import Task

class DriveState():
    def __init__(self, x: int, y: int, theta: float, finished: bool, task: Task | None, stopped: bool, direction: int = 1):
        self.x = x
        self.y = y
        self.theta = theta
        self.finished = finished
        self.task = task
        self.stopped = stopped
        self.direction = direction  # 1: forward, 0: turn, -1: backwards