import asyncio
from rplidar import RPLidar
from typing import List, Tuple, Optional

class Lidar:
    def __init__(self, port: str):
        self.port = port
        self.lidar: Optional[RPLidar] = None
        self.obstacle_threshold = 500  # 500mm = 50cm detection threshold
        self.critical_angles = [(0, 30), (330, 360)]  # Front-facing detection zone
    
    async def connect(self):
        """Async method to establish Lidar connection"""
        self.lidar = RPLidar(self.port)
    
    async def async_process_scan(self) -> bool:
        """
        Asynchronously process a single scan
        Returns:
        - True if path is clear
        - False if obstacle detected
        """
        if not self.lidar:
            await self.connect()
        
        try:
            # Process one full rotation of measurements
            obstacles = await self._check_for_obstacles()
            return not obstacles
        except Exception as e:
            print(f"Lidar scan error: {e}")
            return True  # Assume path is clear on error
    
    async def _check_for_obstacles(self) -> bool:
        """
        Check for obstacles in critical detection zones
        Returns True if obstacles are detected, False otherwise
        """
        # Collect measurements for one full rotation
        measurements = []
        for _ in range(300):  # Collect one full rotation
            try:
                measurement = await self._get_next_measurement()
                if measurement:
                    measurements.append(measurement)
            except StopAsyncIteration:
                break
        
        # Analyze measurements for obstacles
        return self._analyze_measurements(measurements)
    
    async def _get_next_measurement(self) -> Optional[Tuple[bool, float, float, float]]:
        """
        Async generator to get next Lidar measurement
        Yields individual measurements with small async delays
        """
        if not self.lidar:
            raise RuntimeError("Lidar not connected")
        
        # Simulate async iteration
        for measurement in self.lidar.iter_measures():
            await asyncio.sleep(0.001)  # Tiny delay to prevent blocking
            return measurement
        
        raise StopAsyncIteration
    
    def _analyze_measurements(self, measurements: List[Tuple[bool, float, float, float]]) -> bool:
        """
        Analyze collected measurements for obstacles
        
        Args:
            measurements: List of Lidar measurements
        
        Returns:
            True if obstacles detected, False if path is clear
        """
        for measurement in measurements:
            # Unpack measurement
            is_new, quality, angle, distance = measurement
            
            # Check if this is a new reading and within critical zones
            if is_new:
                for (start, end) in self.critical_angles:
                    # Check if angle is within critical detection zone
                    if start <= angle <= end or (start > end and (angle >= start or angle <= end)):
                        # Check if distance is less than threshold
                        if distance < self.obstacle_threshold:
                            return True  # Obstacle detected
        
        return False  # No obstacles detected
    
    async def close(self):
        """
        Async method to safely close Lidar connection
        """
        if self.lidar:
            self.lidar.stop()
            self.lidar.disconnect()
            self.lidar = None
