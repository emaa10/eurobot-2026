from modules.STservo_sdk import * 

BAUDRATE                    = 1000000           # STServo default baudrate : 1000000
STS_MOVING_SPEED            = 2400          # SCServo moving speed
STS_MOVING_ACC              = 50            # SCServo moving acc

class Servos:
    def __init__(self, port = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083062-if00") -> None:
        self.port_handler = PortHandler(port)
        self.packet_handler = sts(self.port_handler)

        # Open port
        if self.port_handler.openPort():
            print("Succeeded to open the port")
        else:
            print("Failed to open the port")
            quit()

        # Set port baudrate
        if self.port_handler.setBaudRate(BAUDRATE):
            print("Succeeded to change the baudrate")
        else:
            print("Failed to change the baudrate")
            quit()

    def write_servo(self, id, goal_position):
        self.packet_handler.WritePosEx(id, goal_position, STS_MOVING_SPEED, STS_MOVING_ACC)