class Position():
    def __init__(self, x, y, theta=0):
        self.x = x
        self.y = y
        self.theta = theta
        
        self.limit()
        
    def limit(self):
        if(self.x > 2999):
            self.x = 2999
        elif(self.x < 0):
            self.x = 0
        
        if(self.y > 1999):
            self.y = 1999
        elif(self.y < 0):
            self.y = 0