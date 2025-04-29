import threading
import logging
from time import time_ns
import queue
from rplidar import RPLidar

class Lidar:
    def __init__(self, port: str = '/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0'):
        self.port = port
        self.lidar = None
        
        self.logger = logging.getLogger(__name__)
        
        # Queue to store scan results
        self.scan_results = queue.Queue(maxsize=10)
        
        # Control flags
        self.running = False
        self.thread = None
    
    def connect(self):
        """Connect to the Lidar device"""
        try:
            self.lidar = RPLidar(self.port)
            self.logger.info("Lidar connected successfully")
            return True
        except Exception as e:
            self.logger.info(f"Failed to connect to Lidar: {e}")
            return False
    
    def start_scanning(self):
        """Start the scanning thread"""
        if self.running:
            return False
        
        if not self.lidar:
            success = self.connect()
            if not success:
                return False
        
        self.running = True
        self.thread = threading.Thread(target=self._scan_loop)
        self.thread.daemon = False
        self.thread.start()
        self.logger.info("Scan thread started")
        return True
    
    def _scan_loop(self):
        """Background thread for continuous scanning"""
        try:
            self.logger.info("Scan loop started")
            time_stamp = time_ns()
            
            # Reset scan data
            current_scan_data = []
            
            for measurement in self.lidar.iter_measures():
                if not self.running:
                    break
                
                new_reading, quality, angle, distance = measurement
                
                # Process only if this is part of a new scan
                if new_reading:
                    # Calculate and self.logger.info time for a complete scan
                    scan_time_ms = (time_ns() - time_stamp) // 1000000
                    # self.logger.info(f"Scan time: {scan_time_ms}ms")
                    time_stamp = time_ns()
                    
                    # Put result in queue, non-blocking
                    try:
                        self.scan_results.put_nowait(current_scan_data)
                    except queue.Full:
                        # Queue is full, get the oldest item first (non-blocking)
                        try:
                            self.scan_results.get_nowait()
                            self.scan_results.put_nowait(current_scan_data)
                        except (queue.Empty, queue.Full):
                            # Handle rare race condition
                            pass
                
                    # Clear scan data for next iteration
                    current_scan_data = []
                    
                # Store valid measurements
                if quality > 10 and distance > 0:  
                    current_scan_data.append((angle, distance))
                
        except Exception as e:
            self.logger.info(f"Error in scan loop: {e}")
                
        finally:
            if self.running:  # Only self.logger.info if we didn't deliberately stop
                self.logger.info("Scan loop ended unexpectedly")
            self.running = False
    
    
    def get_latest_scan(self):
        """
        Get the latest scan result with timeout
        Returns: Boolean (True = path clear, False = obstacle detected)
                 or None if no data available
        """
        try:
            return self.scan_results.get_nowait()
        except queue.Empty:
            return None
    
    def is_running(self):
        """Check if the Lidar thread is still running"""
        return self.running and self.thread and self.thread.is_alive()
    
    def stop(self):
        """Stop the scanning thread safely"""
        # Signal thread to stop
        self.running = False
        
        if self.thread:
            # Wait for thread to finish with timeout
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                self.logger.info("Warning: Lidar thread didn't exit cleanly")
            self.thread = None
        
        if self.lidar:
            try:
                self.lidar.stop()
                self.lidar.disconnect()
            except Exception as e:
                self.logger.info(f"Error stopping Lidar: {e}")
            
            self.lidar = None
        
        self.logger.info("Lidar stopped")

# Example usage
def main():
    lidar = Lidar()  # Update with your port
        
    try:
        print("Starting Lidar scanning")
        if not lidar.start_scanning():
            print("Failed to start Lidar")
            return
    
    except KeyboardInterrupt:
        print("Interrupted by user")
    
    finally:
        print("Stopping Lidar...")
        lidar.stop()

if __name__ == "__main__":
    main()