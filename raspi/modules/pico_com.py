import serial
import time
import logging
from gpiozero import AngularServo

class Pico():
    def __init__(self, port="/dev/serial/by-id/usb-Raspberry_Pi_Pico_503558607AD3331F-if00", baud_rate=115200) -> None:
        self.ser = serial.Serial(port, baud_rate, timeout=1)
        
        self.ser.setDTR(False)
        time.sleep(1)
        self.ser.flushInput()
        self.ser.setDTR(True)
        time.sleep(1)
        
        self.logger = logging.getLogger(__name__)
        
        self.servo_rotate_left = AngularServo(12, min_pulse_width=0.0006, max_pulse_width=0.0023)
            
    def get_status(self) -> str | None:
        # flush input to get the latest data
        self.ser.flushInput()

        line = self.ser.readline().decode("utf-8")
        
        if line:
            return line[:-2]
        
    def wait_for_ok(self):
        while True:
            status = self.get_status()
            if status == 'ok': 
                break
        
    def set_command(self, command: str, value: int) -> None:
        command_string = f"{command}{value}\n"
        byte_string = str.encode(command_string)
        self.ser.write(byte_string)



    # 1: unteres brett, 2: oberes brett, 3: zweite ebene brett, 4: ganz oben, 5: über 2. brett
    def set_mid_stepper(self, command: int):
        if(command == 1): self.set_command("b", 270)
        elif(command == 2): self.set_command("b", 600)
        elif(command == 3): self.set_command("b", 2650)
        elif(command == 4): self.set_command("b", 3375)
        elif(command == 5): self.set_command("b", 1000)

    # 1: grip_down, 2: anfahren unten, 3: ablegen oben, 4: vor ablegen oben
    def set_right_stepper(self, command: int):
        if(command == 1): self.set_command("a", 40)
        elif(command == 2): self.set_command("a", 280)
        elif(command == 3): self.set_command("a", 710)
        elif(command == 4): self.set_command("a", 810)

    # 1: up grip, 2: down grip
    def set_left_servo(self, command: int):
        if(command == 1):
            self.set_command("r", 40)
        else:
            self.set_command("r", 160)
                        
    # 1: fully open, 2: grip plate, 3: collision avoidance, 4: closed
    def set_plate_gripper(self, command: int):
        if(command == 1): self.set_command("s", 175)
        elif(command == 2): self.set_command("s", 120)
        elif(command == 3): self.set_command("s", 130)
        elif(command == 4): self.set_command("s", 0)

    # 1: up, 2: down
    def set_drive_flag(self, command: int):
        if(command == 1):
            self.set_command("t", 20)
        else:
            self.set_command("t", 165)

    # 1: open, 2: closed 3: home
    def set_grip_right(self, command: int):
        if(command == 1):
            self.set_command("v", 80)
        elif(command == 2):
            self.set_command("v", 30)
        elif(command == 3):
            self.set_command("v", 50)

    # 1: closed, 2: open
    def set_grip_left(self, command: int):
        if(command == 1):
            self.set_command("y", 150)
        elif(command == 2):
            self.set_command("y", 75)
        elif(command == 3):
            self.set_command("y", 110)
            
    # 1: outwards, 2: inwards, 3: deposit, 4: mid, 5: grip cans
    def set_servo_rotate_right(self, command: int):
        if(command == 1): self.set_command("w", 15)
        elif(command == 2): self.set_command("w", 170)
        elif(command == 3): self.set_command("w", 146)
        elif(command == 4): self.set_command("w", 110)
        elif(command == 5): self.set_command("w", 110)

    # 1: outwards, 2: inwards, 3: deposit, 4: mid, 5: grip cans
    def set_servo_rotate_left(self, command: int):
        if not self.servo_rotate_left: 
            self.servo_rotate_left = AngularServo(12, min_pulse_width=0.0006, max_pulse_width=0.0023)
        if(command == 1): self.servo_rotate_left.angle = 87
        elif(command == 2): self.servo_rotate_left.angle = -60
        elif(command == 3): self.servo_rotate_left.angle = 50
        elif(command == 4): self.servo_rotate_left.angle = 25
        elif(command == 5): self.servo_rotate_left.angle = 0
        time.sleep(1)
        # self.servo_rotate_left.detach()
        # self.servo_rotate_left = None
        
    def emergency_stop(self):
        self.set_command("e", 0)
        if self.servo_rotate_left: self.servo_rotate_left.detach()
        self.servo_rotate_left = None

    def prepare_gripping(self):
        self.set_servo_rotate_right(1)
        self.set_servo_rotate_left(1)
        self.set_grip_right(3)
        self.set_grip_left(3)
        self.set_left_servo(1)
        self.set_right_stepper(2)
        self.set_mid_stepper(5)

        self.set_plate_gripper(1)
        self.set_mid_stepper(5)

    # 1: beide, 2: nur links, 3: nur rechts
    def grip_stapel(self, which=1):
        # plate grippen, ganz hoch fahren wg greifen
        # self.set_plate_gripper(1)
        # self.set_mid_stepper(1)
        # self.set_plate_gripper(2)
        self.set_mid_stepper(1)
        time.sleep(1)
        self.set_plate_gripper(2)
        time.sleep(1)
        self.set_mid_stepper(4)
        time.sleep(1)

        # reindrehen und hochfahren
        if which == 1 or which == 2: self.set_servo_rotate_left(5) # rein drehen
        if which == 1 or which == 3: self.set_servo_rotate_right(5)
        time.sleep(1)

        if which == 1 or which == 2: self.set_grip_left(2) #auf
        if which == 1 or which == 3: self.set_grip_right(1)
        time.sleep(1)

        if which == 1 or which == 2: self.set_left_servo(2) #runter fahren
        if which == 1 or which == 3: self.set_right_stepper(1)
        time.sleep(1)

        if which == 1 or which == 2: self.set_grip_left(1) #zu
        if which == 1 or which == 3: self.set_grip_right(2)
        time.sleep(1)

        if which == 1 or which == 2: self.set_left_servo(1) # hoch fahren
        if which == 1 or which == 3: self.set_right_stepper(4)
        time.sleep(1)

        if which == 1 or which == 2: self.set_servo_rotate_left(1) # raus drehen
        if which == 1 or which == 3: self.set_servo_rotate_right(1)
        time.sleep(1)

    # 1: beide, 2: nur links, 3: nur rechts
    def deposit_stapel(self, which=1):
        self.set_servo_rotate_left(2) # in mitte
        time.sleep(2)
        self.set_left_servo(2) # runter fahren
        time.sleep(2)
        self.set_grip_left(2)  #loslassen
        time.sleep(2)
        self.set_left_servo(1) # hoch fahren
        time.sleep(2)
        self.set_servo_rotate_left(1) # rausdrehen
        time.sleep(2)

        self.set_mid_stepper(1) # zum unteren brett runter
        time.sleep(2.5)
        self.set_plate_gripper(1) # gripper auf
        time.sleep(2)
        self.set_mid_stepper(2) # zum oberen brett
        time.sleep(2)
        self.set_plate_gripper(2) # zu machen
        time.sleep(2)
        self.set_mid_stepper(4) # ganz hoch fahren
        time.sleep(2)

        self.set_servo_rotate_right(3) # rechten zum ablegen drehen
        time.sleep(2)
        self.set_right_stepper(4) # zum ablegen runterfahren
        time.sleep(2)
        self.set_grip_right(1) # aufmachen
        time.sleep(2)

        self.set_mid_stepper(4) # mittleren stepper hoch
        time.sleep(2) 
        self.set_servo_rotate_right(1) # right rausdrehen
        time.sleep(2)
        self.set_mid_stepper(3) # zum zweiten brett fahren oben
        time.sleep(2)
        self.set_plate_gripper(1) # gripper auf
        time.sleep(2)
        self.set_mid_stepper(4) # ganz hoch steper
        time.sleep(2)




    def collission_free_sevors(self):
        self.set_drive_flag(1)
        self.set_left_servo(2)
        time.sleep(0.2)
        self.set_plate_gripper(3)
        time.sleep(0.2)
        self.set_drive_flag(1)
        time.sleep(0.2)
        self.set_grip_right(3)
        time.sleep(0.2)
        self.set_grip_left(3)
        time.sleep(0.2)
        self.set_servo_rotate_right(1)
        time.sleep(0.2)
        self.set_servo_rotate_left(1)
        
    def position_sevors(self):
        self.set_plate_gripper(4)
        self.set_servo_rotate_right(2)
        self.set_servo_rotate_left(2)
        
    def home_pico(self):
        self.collission_free_sevors()
        self.set_command("h", 0)
        self.wait_for_ok()
        self.position_sevors()
        
def main():
    serial_manager = Pico()
    time.sleep(1)

    # serial_manager.set_servo_rotate_left(3)
    # serial_manager.home_pico()
    # time.sleep(10)
    # # serial_manager.set_servo_rotate_left(2)
    # serial_manager.prepare_gripping()
    # time.sleep(10)
    # serial_manager.grip_stapel()
    # time.sleep(10)
    # serial_manager.set_servo_rotate_left(5)
    # serial_manager.set_servo_rotate_right(5)
    # serial_manager.set_grip_left(2)
    
    # serial_manager.set_command('s', 130)
    # serial_manager.set_command('h', 0)
    # serial_manager.wait_for_ok()
    # print('done')
    
    serial_manager.set_servo_rotate_left(1)
        
if __name__ == '__main__':
    main()