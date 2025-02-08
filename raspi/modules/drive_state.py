class DriveState():
    def __init__(self, x: int, y: int, theta: float, finished: bool):
        self.x = x
        self.y = y
        self.theta = theta
        self.finished = finished