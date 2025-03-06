from rplidar import RPLidar
from drive_state import DriveState
from time import time_ns

PORT_NAME = '/dev/tty.usbserial-0001'

class Lidar():
    def __init__(self, port: str):
        self.lidar = RPLidar(port)

    def run(self):
        print('Recording measurments... Press Crl+C to stop.')
        
        time_stamp = time_ns()
        counter = 0
        
        for measurment in self.lidar.iter_measures():
            new_reading = measurment[0]
            angle = measurment[2]
            distance = measurment[3]
            counter += 1
            
            if new_reading:
                dif = (time_ns() - time_stamp)
                print(dif)
                print(counter)
                counter = 0
                time_stamp = time_ns()
            
            # print(f'angle: {angle}, distance: {distance}')

        self.lidar.stop()
        self.lidar.disconnect()

if __name__ == '__main__':
    lidar = Lidar(PORT_NAME)
    lidar.run()