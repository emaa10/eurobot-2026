class SimplePID:
    def __init__(self):
        # Parameters
        self.kp = 0.45
        self.kd = 0.005
        self.ki = 0.0
        self.umax = 100.0
                
        # Storage
        self.eprev = 0.0
        self.eintegral = 0.0
    
    def evaluate(self, value1: int, value2: int, target1: int, target2: int, delta_t: float) -> list[int, int]:
        """Compute the control signal.
        
        Args:
            value1: First current value
            value2: Second current value
            target1: First target value
            target2: Second target value
            delta_t: Time step
            
        Returns:
            list containing:
                - power: Absolute magnitude of control signal
                - direction: Direction of control (1: forward, -1: reverse, 0: stop)
        """
        # Error
        e1 = target1 - value1
        e2 = target2 - value2
        
        # Derivative
        dedt = (abs(value2) - abs(value1)) / delta_t
        dedt = -dedt if e1 < 0 else dedt
        if self.kp * e1 < 255 or self.kp * e2 < 255:
            dedt = 0
        
        # Integral
        self.eintegral += e1 * delta_t
        
        # Control signal
        u = self.kp * e1 + self.kd * dedt + self.ki * self.eintegral
        
        # Motor power (magnitude)
        power = int(abs(u))
        
        # Motor direction
        if u > 0:
            direction = 1
        elif u < 0:
            direction = -1
        else:
            direction = 0
        
        # Store previous error
        self.eprev = e1
        
        return power, direction