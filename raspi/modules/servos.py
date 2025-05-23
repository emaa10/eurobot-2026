from modules.STservo_sdk import * 

BAUDRATE                    = 1000000           # STServo default baudrate : 1000000
STS_MOVING_SPEED            = 2400          # SCServo moving speed
STS_MOVING_ACC              = 50            # SCServo moving acc

class Servos:
    def parse_servo_pos(self):
        result = []
        with open('/home/eurobot/main-bot/raspi/modules/servo.txt', 'r') as file:
            for line in file:
                line = line.split('#')[0].strip()
                if not line:
                    continue
                parts = line.split(',')
                id_ = int(parts[0])
                values = list(map(int, parts[1:]))
                result.append([id_, values])
        return result

    def __init__(self, port = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083062-if00") -> None:
        self.port_handler = PortHandler(port)
        self.packet_handler = sts(self.port_handler)
        self.servoPos = self.parse_servo_pos()

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

    # 1: oben, 2: unten
    def servo_mitte_lift(self, pos: int):
        value = 0 
        if pos == 1: value = self.servoPos[0][1][0]
        else: value = self.servoPos[0][1][1]
        self.write_servo(self.servoPos[0][0], value)

    # 1: auf, 2: zu
    def servo_mitte_grip(self, pos: int):
        value = 0 
        match pos:
            case 1: value = self.servoPos[1][1][0]
            case 2: value = self.servoPos[1][1][1]
            case _: value = self.servoPos[1][1][2]

        self.write_servo(self.servoPos[1][0], value)

    # 1: außen, 2: mitte, 3: innen
    def servo_right_rotate(self, pos: int):
        value = 0 
        if pos == 1: value = self.servoPos[2][1][0]
        elif pos == 2: value = [2][1][1]
        else: value = [2][1][2]
        self.write_servo(self.servoPos[2][0], value)

    # 1: oben, 2: unten
    def servo_plate_rotate(self, pos: int):
        value = 0 
        if pos == 1: value = self.servoPos[3][1][0]
        else: value = self.servoPos[3][1][1]
        self.write_servo(self.servoPos[3][0], value)

    # 1: auf, 2: zu
    def servo_right_grip(self, pos: int):
        value = 0 
        if pos == 1: value = self.servoPos[4][1][0]
        else: value = self.servoPos[4][1][1]
        self.write_servo(self.servoPos[4][0], value)

    # 1: auf, 2: zu
    def servo_left_grip(self, pos: int):
        value = 0 
        if pos == 1: value = self.servoPos[5][1][0]
        else: value = self.servoPos[5][1][1]
        self.write_servo(self.servoPos[5][0], value)

    # 1: außen, 2: mitte, 3: innen
    def servo_left_rotate(self, pos: int):
        value = 0 
        if pos == 1: value = self.servoPos[6][1][0]
        elif pos == 2: value = [6][1][1]
        else: value = self.servoPos[6][1][2]
        self.write_servo(self.servoPos[6][0], value)

    # 1: auf, 2: zu
    def servo_plate_grip(self, pos: int):
        value = 0 
        if pos == 1: value = self.servoPos[7][1][0]
        else: value = self.servoPos[7][1][1]
        self.write_servo(self.servoPos[7][0], value)
        
    def pos_anfahren(self):
        self.servo_left_rotate(2)
        self.servo_right_rotate(2)
        self.servo_mitte_lift(2)
        self.servo_mitte_grip(3)
        self.servo_left_grip(1)
        self.servo_right_grip(1)
        self.servo_plate_rotate(2)
        self.servo_plate_grip(1)
        
    def grip_cans(self):
        self.servo_mitte_grip(2)
        self.servo_left_grip(2)
        self.servo_right_grip(2)
        self.servo_plate_grip(2)
        time.sleep(0.4)
        self.servo_left_rotate(1)
        self.servo_right_rotate(1)
    
    def cans_in(self):
        self.servo_left_rotate(3)
        self.servo_right_rotate(3)
        
    def place_1er(self, num: int):
        if num == 1:
            self.servo_mitte_lift(2)
            time.sleep(0.3)
            self.servo_mitte_grip(1)
        else:
            self.servo_plate_grip(1)
            self.servo_left_grip(1)
            self.servo_right_grip(1)
        
        
    def place_2er(self):
        self.servo_mitte_lift(2)
        time.sleep(0.3)
        self.servo_mitte_grip(1)
        self.servo_left_grip(1)
        self.servo_right_grip(1)
        self.servo_plate_grip(1)
        time.sleep(0.3)
        self.servo_plate_rotate(1)
        
    def pos_wegfahren(self):
        self.servo_mitte_lift(1)
        
    def grip_unten(self):
        self.servo_left_grip(2)
        self.servo_right_grip(2)
        
    def release_außen(self):
        self.servo_left_grip(1)
        self.servo_right_grip(1)
        
def main():
    servos = Servos()
    servos.servo_mitte_lift(1)
    
if __name__ == '__main__':
    main()