class DriveState():
    def __init__(self, x: int, y: int, theta: float, finished: bool, direction: bool = True):
        self.x = x
        self.y = y
        self.theta = theta
        self.finished = finished
        self.direction = direction