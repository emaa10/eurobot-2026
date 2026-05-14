import threading
import logging
import queue
import math
from time import time_ns, sleep, time
from pyrplidar import PyRPlidar

class Lidar:
    def __init__(self, port: str = '/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_ee5a3b581464ef1196f5daa9c169b110-if00-port0'):
        self.port = port
        self.lidar = None
        
        self.logger = logging.getLogger(__name__)
        
        # Queue to store scan results
        self.scan_results = queue.Queue(maxsize=10)
        self.latest_scan_time = time()
        
        # Control flags
        self.running = False
        self.thread = None
        self.stop_motor = False
        self.arms_up = False
        self._last_live_log = 0.0
    
    def connect(self):
        """Connect to the Lidar device"""
        try:
            self.lidar = PyRPlidar()
            self.lidar.connect(port=self.port, baudrate=460800, timeout=5)
            self.lidar.stop()
            sleep(0.1)
            self.lidar.set_motor_pwm(660)
            sleep(1.0)
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
        self.logger.info("Scan loop started")
        time_stamp = time_ns()
        
        # Reset scan data
        current_scan_data = []
        
        
        while True:
            try:
                scan_generator = self.lidar.start_scan()
                for count, measurement in enumerate(scan_generator()):                 
                    if measurement.start_flag:          
                        try:
                            self.scan_results.put_nowait(current_scan_data)
                        except queue.Full:
                            self.scan_results.get_nowait()
                            self.scan_results.put_nowait(current_scan_data)

                        current_scan_data = []
                        
                    if measurement.quality > 0 and measurement.distance > 0:
                        current_scan_data.append((measurement.angle, measurement.distance))
            
            except Exception as e:
                if not self.running:
                    break
                
    
    def get_latest_scan(self):
        """
        Get the latest scan result with timeout
        Returns: List of (angle, distance) tuples or None if no data available
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
                self.lidar.set_motor_pwm(0)
                self.lidar.disconnect()
            except Exception as e:
                self.logger.info(f"Error stopping Lidar: {e}")
            
            self.lidar = None
        
        self.logger.info("Lidar stopped")
        
    # Erkennungsparameter
    STOP_DIST          = 250   # mm  Stoppschwelle (25cm)
    STOP_DIST_ARMS_UP  = 630   # mm  Stoppschwelle vorwärts wenn Arme oben (+20cm)
    CONE_DEG   = 60.0  # °   halber Kegelwinkel voraus/rückwärts (±60° = 120° gesamt)
    MIN_DIST   = 70    # mm  Eigenkörper ignorieren
    MIN_HITS   = 3     # Punkte für sicheren Treffer
    ANGLE_OFFSET = 270  # °   Montage-Rotation des Lidars (Lidar 180° gedreht → vorne=270°)

    @staticmethod
    def _in_cone(angle, center_deg, half_deg):
        diff = (angle - center_deg + 180) % 360 - 180
        return abs(diff) <= half_deg

    def get_stop(self, x, y, theta, direction) -> bool:
        """direction: +1 vorwärts, -1 rückwärts, 0 drehen → Vollkreis-Check."""
        if self.latest_scan_time + 0.02 > time():
            return self.stop_motor

        latest_scan = self.get_latest_scan()
        self.latest_scan_time = time()

        if not latest_scan:
            return self.stop_motor

        prev_stop = self.stop_motor
        self.stop_motor = False
        obstacles = 0
        closest_dist = None
        closest_angle = None
        for angle, distance in latest_scan:
            if distance < self.MIN_DIST:
                continue

            # Kegelfilter + Stoppdistanz: vorwärts mit Armen oben 20cm weiter
            if direction > 0:
                if not self._in_cone(angle, (0 + self.ANGLE_OFFSET) % 360, self.CONE_DEG):
                    continue
                stop_dist = self.STOP_DIST_ARMS_UP if self.arms_up else self.STOP_DIST
            elif direction < 0:
                if not self._in_cone(angle, (180 + self.ANGLE_OFFSET) % 360, self.CONE_DEG):
                    continue
                stop_dist = self.STOP_DIST
            else:
                stop_dist = self.STOP_DIST

            if distance > stop_dist:
                continue

            if closest_dist is None or distance < closest_dist:
                closest_dist = distance
                closest_angle = angle
            obstacles += 1
            if obstacles >= self.MIN_HITS:
                self.stop_motor = True
                break

        now = time()
        if self.stop_motor and not prev_stop:
            self.logger.info(
                f'GEGNER ERKANNT – Stop! {closest_dist:.0f}mm @ {closest_angle:.1f}°'
            )
            self._last_live_log = now
        elif not self.stop_motor and prev_stop:
            self.logger.info('Weg frei – Fahrt fortgesetzt')
        elif self.stop_motor and now - self._last_live_log >= 0.333:
            self.logger.info(f'Gegner: {closest_dist:.0f}mm @ {closest_angle:.1f}°')
            self._last_live_log = now

        return self.stop_motor

# Example usage
def main():
    lidar = Lidar()  # Update with your port
        
    try:
        print("Starting Lidar scanning")
        if not lidar.start_scanning():
            print("Failed to start Lidar")
            return
        
        while True:
            test = lidar.get_stop(1800, 1000, 270, 0)
            sleep(0.02)
                    
    
    except KeyboardInterrupt:
        print("Interrupted by user")
    
    finally:
        print("Stopping Lidar...")
        lidar.stop()

if __name__ == "__main__":
    main()