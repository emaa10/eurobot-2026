from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QTimer
import sys
import os
import time
# import asyncio
import subprocess
import threading
import socket
import logging

HOST = '127.0.0.1'
PORT = 5001

class general:
    def __init__(self):
        self.pullcord_pulled = False

        self.start_server()
        threading.Thread(target=self.receive_messages, daemon=True).start()

        logging.basicConfig(filename='/home/eurobot/main-bot/raspi/eurobot.log', level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        
    async def l(self, msg: str):
        print(msg)
        self.logger.info(msg)

        
    ## ! ggf umschreiben dass es im terminal minimiert aufgeht
    def start_server(self):
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                pass
        except:
            # subprocess.Popen(["python3", "main.py"])
            pass

    def send_input(self, msg):
        # msg = self.input_field.text().strip()
        if not msg:
            return
        with socket.create_connection((HOST, PORT), timeout=1) as s:
            s.sendall(msg.encode())

    def receive_messages(self):
        while True:
            try:
                with socket.create_connection((HOST, PORT), timeout=1) as s:
                    data = s.recv(1024).decode()
                    if data:
                        command = data[0]
                        value1 = int(data[1:])
                        value2 = 0
                        if(len(data)): value2=int(data[3])

                        if command == "p":
                            if(value1 == 1): self.pullcord_pulled = True 
                            else: self.pullcord_pulled = False
            except Exception as e:
                self.l(f"Fehler beim Empfangen von Nachrichten: {e}")


class MainScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        General = general()
        
        self.selected_color = None
        self.selected_position : int | None = None
        self.selected_tactic = None

        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()
        
        self.initUI()

    def initUI(self):
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(6)

        self.add_close_and_stop_buttons(self.layout, self.stop_everything)

        color_layout = QtWidgets.QHBoxLayout()
        color_layout.setSpacing(4)
        self.color_group = QtWidgets.QButtonGroup()
        
        self.yellow_btn = QtWidgets.QPushButton("GELB")
        self.yellow_btn.setFixedSize(200, 60)
        self.yellow_btn.setStyleSheet("""
            QPushButton { background-color: #ffff00; font-size: 28px; border: 2px solid black; border-radius: 8px; }
            QPushButton:checked { border: 3px solid #00ff00; }
        """)
        self.yellow_btn.setCheckable(True)
        
        self.blue_btn = QtWidgets.QPushButton("BLAU")
        self.blue_btn.setFixedSize(200, 60)
        self.blue_btn.setStyleSheet("""
            QPushButton { background-color: #0000ff; color: white; font-size: 28px; border: 2px solid black; border-radius: 8px; }
            QPushButton:checked { border: 3px solid #00ff00; }
        """)
        self.blue_btn.setCheckable(True)
        
        self.color_group.addButton(self.yellow_btn)
        self.color_group.addButton(self.blue_btn)
        self.color_group.buttonToggled.connect(self.on_color_changed)
        
        color_layout.addStretch()
        color_layout.addWidget(self.yellow_btn)
        color_layout.addWidget(self.blue_btn)
        color_layout.addStretch()
        self.layout.addLayout(color_layout)

        # Field and Status Side-by-Side
        field_status_layout = QtWidgets.QHBoxLayout()
        field_status_layout.setSpacing(6)
        
        # Spielfeld Container als QLabel
        self.field_container = QtWidgets.QLabel()
        self.field_container.setFixedSize(1000, 380)
        self.field_container.setStyleSheet("background-color: #ffffff; border: 2px solid black;")
        self.field_container.setAlignment(QtCore.Qt.AlignCenter)

        # Bild laden und skalieren
        image_path = os.path.expanduser("~/main-bot/raspi/eurobot.png")
        if os.path.exists(image_path):
            pixmap = QtGui.QPixmap(image_path)
            pixmap = pixmap.scaled(980, 380, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.field_container.setPixmap(pixmap)

        field_status_layout.addWidget(self.field_container)
        self.layout.addLayout(field_status_layout)

        # Taktik Buttons
        tactics_layout = QtWidgets.QHBoxLayout()
        tactics_layout.setSpacing(4)
        self.tactic_buttons = []
        for i in range(4):
            btn = QtWidgets.QPushButton(f"TAKTIK {i+1}")
            btn.setFixedSize(180, 50)
            btn.setStyleSheet("""
                QPushButton { font-size: 20px; background-color: #f0f0f0; border-radius: 6px; }
                QPushButton:checked { background-color: white; border: 2px solid black; }
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, x=i+1: self.on_tactic_selected(x))
            self.tactic_buttons.append(btn)
            tactics_layout.addWidget(btn)
        self.layout.addLayout(tactics_layout)

        # Start/Debug Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(4)
        self.start_btn = QtWidgets.QPushButton("START")
        self.start_btn.setFixedSize(160, 50)
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet("""
            QPushButton { font-size: 28px; background-color: #808080; color: white; border-radius: 8px; }
            QPushButton:enabled { background-color: #00ff00; color: black; }
        """)
        
        self.debug_btn = QtWidgets.QPushButton("DEBUG")
        self.debug_btn.setFixedSize(160, 50)
        self.debug_btn.setStyleSheet("font-size: 28px; border-radius: 8px;")
        
        button_layout.addStretch()
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.debug_btn)
        button_layout.addStretch()
        self.layout.addLayout(button_layout)

        self.setLayout(self.layout)

    def add_close_and_stop_buttons(self, layout, stop_callback):
        button_layout = QtWidgets.QHBoxLayout()
        stop_btn = QtWidgets.QPushButton("STOP")
        stop_btn.setFixedSize(100, 40)
        stop_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        stop_btn.clicked.connect(stop_callback)

        close_btn = QtWidgets.QPushButton("X")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        close_btn.clicked.connect(QtWidgets.QApplication.quit)

        button_layout.addWidget(stop_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def stop_everything(self):
        self.main_controller.pico_controller.set_command('e', 0) # stop all pico actions
        self.async_runner.run_task(self.main_controller.motor_controller.set_stop())
        time.sleep(1)
        os.system("pkill python3")

    def on_color_changed(self, button, checked):
        if checked:
            self.selected_color = button.text()
            positions = yellow_positions if button == self.yellow_btn else blue_positions
            self.show_position_rectangles(positions)
        self.check_selections()

    def show_position_rectangles(self, positions):
        for btn in getattr(self, 'position_buttons', []):
            btn.deleteLater()
        self.position_buttons = []
        for pos in positions:
            btn = QtWidgets.QPushButton(self.field_container)
            btn.setGeometry(QtCore.QRect(*pos))
            btn.setStyleSheet("""
                QPushButton { background-color: rgba(255,0,0,30); border: 2px solid #ff0000; border-radius: 4px; }
                QPushButton[selected=\"true\"] { background-color: rgba(0,255,0,50); border: 2px solid #00ff00; }
            """)
            btn.clicked.connect(self.create_position_click_handler(pos))
            btn.show()
            self.position_buttons.append(btn)

    def create_position_click_handler(self, position):
        def handler():
            for btn in self.position_buttons:
                btn.setProperty("selected", False)
                btn.style().polish(btn)
            self.sender().setProperty("selected", True)
            self.sender().style().polish(self.sender())
            self.selected_position = position
            self.check_selections()
        return handler

    ###############################################################
    def on_tactic_selected(self, tactic):
        for btn in self.tactic_buttons:
            btn.setChecked(False)
        self.tactic_buttons[tactic-1].setChecked(True)
        self.selected_tactic = tactic
        self.check_selections()

    def check_selections(self):
        enable = all([self.selected_color, self.selected_position, self.selected_tactic])
        self.start_btn.setEnabled(enable)


class DebugScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Main = main()
        General = general()

        self.robot_data = {'x': 0.0, 'y': 0.0, 'angle': 0.0, 'goal_x': 100.0, 'goal_y': 200.0}
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.add_close_and_stop_buttons(layout, self.stop_everything)

        btns = [
            ("Shutdown", self.on_shutdown),
            # ("Test Codes", self.on_test_codes),
            ("Pico Codes", self.on_pico_codes),
            ("Show Keyboard", self.on_show_keyboard),
            # ("Clean Wheels", self.on_clean_wheels),
            ("Show Camera Stream", self.on_show_camera),
            ("Log Tail", self.on_log_tail)
        ]
        for text, handler in btns:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedHeight(60)
            btn.setStyleSheet("font-size: 20px; border-radius: 8px;")
            btn.clicked.connect(handler)
            layout.addWidget(btn)

        back_btn = QtWidgets.QPushButton("Back")
        back_btn.setFixedHeight(50)
        back_btn.setStyleSheet("font-size: 20px; background-color: #ff4444; border-radius: 8px;")
        back_btn.clicked.connect(lambda: window.stacked.setCurrentIndex(0))
        layout.addWidget(back_btn)

        self.setLayout(layout)

    def add_close_and_stop_buttons(self, layout, stop_callback):
        button_layout = QtWidgets.QHBoxLayout()
        stop_btn = QtWidgets.QPushButton("STOP")
        stop_btn.setFixedSize(100, 40)
        stop_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        stop_btn.clicked.connect(stop_callback)

        close_btn = QtWidgets.QPushButton("X")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        close_btn.clicked.connect(QtWidgets.QApplication.quit)

        button_layout.addWidget(stop_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def stop_everything(self):
        self.main_controller.pico_controller.set_command('e', 0) # stop all pico actions
        self.async_runner.run_task(self.main_controller.motor_controller.set_stop())
        time.sleep(1)
        os.system("pkill python3")

    ###############################################################
    def on_shutdown(self): os.system("sudo shutdown now")
    def on_test_codes(self): window.stacked.setCurrentIndex(3)
    def on_pico_codes(self): window.stacked.setCurrentIndex(4)
    def on_show_keyboard(self):
        subprocess.Popen(
            ['lxterminal', '-e', f'wvkbd-mobintl -H 150 -L 250'],
            env=dict(os.environ)
        )
    def on_clean_wheels(self): 
        self.async_runner.run_task(self.main_controller.motor_controller.clean_wheels())
    def on_show_camera(self):
        subprocess.Popen(
            ['lxterminal', '-e', f'python3 /home/eurobot/main-bot/raspi/camera/camera_window.py'],
            env=dict(os.environ)
        )
    def on_log_tail(self):
        """Open new terminal with log tail command"""
        log_path = "/home/eurobot/main-bot/raspi/eurobot.log"  # Update this path to your actual log file
        subprocess.Popen(
            ['lxterminal', '-e', f'tail -f {log_path}'],
            env=dict(os.environ)
        )


class TestCodesScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Main = main()
        General = general()

        self.initUI()

    def driveDistance(self, distance: int):
        coro = self.main_controller.motor_controller.drive_distance(1000)
        self.async_runner.run_task(coro)

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)

        self.add_close_and_stop_buttons(layout, self.stop_everything)


        for text, action in [
            # ("Drive 1m →", lambda: self.main_controller.motor_controller.drive_to_target(30, 30)),
            ("Drive 1m →", lambda: self.driveDistance(1000)),
            # ("Drive 1m →", lambda: self.driveDistance(1000)),
            ("Drive 1m ←", lambda: self.main_controller.motor_controller.drive_distance(-1000)),
            ("Turn 90°", lambda: self.main_controller.motor_controller.turn_angle(90)),
            ("Turn -90°", lambda: self.main_controller.motor_controller.turn_angle(-90)),
            ("Turn 180°", lambda: self.main_controller.motor_controller.turn_angle(180))
        ]:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedHeight(80)
            btn.setStyleSheet("font-size: 24px; border-radius: 10px;")
            btn.clicked.connect(lambda _, a=action: self.async_runner.run_task(a()))
            layout.addWidget(btn)

        back_btn = QtWidgets.QPushButton("Back")
        back_btn.setFixedHeight(60)
        back_btn.setStyleSheet("font-size: 24px; background-color: #ff4444; border-radius: 10px;")
        back_btn.clicked.connect(lambda: window.stacked.setCurrentIndex(1))
        layout.addWidget(back_btn)

        self.setLayout(layout)

    def add_close_and_stop_buttons(self, layout, stop_callback):
        button_layout = QtWidgets.QHBoxLayout()
        stop_btn = QtWidgets.QPushButton("STOP")
        stop_btn.setFixedSize(100, 40)
        stop_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        stop_btn.clicked.connect(stop_callback)

        close_btn = QtWidgets.QPushButton("X")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        close_btn.clicked.connect(QtWidgets.QApplication.quit)

        button_layout.addWidget(stop_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def stop_everything(self):
        self.main_controller.pico_controller.set_command('e', 0) # stop all pico actions
        self.async_runner.run_task(self.main_controller.motor_controller.set_stop())
        time.sleep(1)
        os.system("pkill python3")

class PicoScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Main = main()
        General = general()

        self.mid_stepper_value = 20    # "left"/mid stepper default
        self.right_stepper_value = 100  # right stepper default
        self.initUI()

    def initUI(self):
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(10,10,10,10)
        main_layout.setSpacing(1)

        self.add_close_and_stop_buttons(main_layout, self.stop_everything)

        # --- Stepper controls: one row with four buttons ---
        stepper_group = QtWidgets.QGroupBox()
        stepper_layout = QtWidgets.QHBoxLayout()

        self.create_command_button("Mid stepper unteres brett", lambda: self.main_controller.pico_controller.set_mid_stepper(1), stepper_layout)
        self.create_command_button("Mid Stepper oberes brett", lambda: self.main_controller.pico_controller.set_mid_stepper(2), stepper_layout)
        self.create_command_button("Mid Stepper 2. oben brett", lambda: self.main_controller.pico_controller.set_mid_stepper(3), stepper_layout)
        self.create_command_button("Mid Stepper ganz oben", lambda: self.main_controller.pico_controller.set_mid_stepper(4), stepper_layout)

        stepper_group.setLayout(stepper_layout)
        main_layout.addWidget(stepper_group)

        # --- Stepper2 controls: one row with four buttons ---
        stepper_right_layout = QtWidgets.QHBoxLayout()
        stepper_right_group = QtWidgets.QGroupBox()

        self.create_command_button("Right stepper", lambda: self.step_mid_up, stepper_right_layout)
        self.create_command_button("Right stepper", lambda: self.step_mid_down, stepper_right_layout)
        self.create_command_button("Right stepper", lambda: self.step_right_up, stepper_right_layout)
        self.create_command_button("Right stepper", lambda: self.step_right_down, stepper_right_layout)

        stepper_right_group.setLayout(stepper_right_layout)
        main_layout.addWidget(stepper_right_group)

        # --- Other existing groups ---
        left_servo_group = QtWidgets.QGroupBox()
        left_servo_layout = QtWidgets.QHBoxLayout()
        self.create_command_button("Left Servo Up", lambda: self.main_controller.pico_controller.set_left_servo(1), left_servo_layout)
        self.create_command_button("Left Servo Down", lambda: self.main_controller.pico_controller.set_left_servo(2), left_servo_layout)
        left_servo_group.setLayout(left_servo_layout)
        main_layout.addWidget(left_servo_group)

        plate_gripper_group = QtWidgets.QGroupBox()
        plate_gripper_layout = QtWidgets.QHBoxLayout()
        self.create_command_button("Fully Open", lambda: self.main_controller.pico_controller.set_plate_gripper(1), plate_gripper_layout)
        self.create_command_button("Grip Plate", lambda: self.main_controller.pico_controller.set_plate_gripper(2), plate_gripper_layout)
        self.create_command_button("Collision Avoid", lambda: self.main_controller.pico_controller.set_plate_gripper(3), plate_gripper_layout)
        self.create_command_button("Closed", lambda: self.main_controller.pico_controller.set_plate_gripper(4), plate_gripper_layout)
        plate_gripper_group.setLayout(plate_gripper_layout)
        main_layout.addWidget(plate_gripper_group)

        drive_flag_group = QtWidgets.QGroupBox()
        drive_flag_layout = QtWidgets.QHBoxLayout()
        self.create_command_button("Flag Up", lambda: self.main_controller.pico_controller.set_drive_flag(1), drive_flag_layout)
        self.create_command_button("Flag Down", lambda: self.main_controller.pico_controller.set_drive_flag(2), drive_flag_layout)
        self.create_command_button("Right Grip Closed", lambda: self.main_controller.pico_controller.set_grip_right(1), drive_flag_layout)
        self.create_command_button("Right Grip Open", lambda: self.main_controller.pico_controller.set_grip_right(3), drive_flag_layout)
        drive_flag_group.setLayout(drive_flag_layout)
        main_layout.addWidget(drive_flag_group)

        right_rotate_group = QtWidgets.QGroupBox()
        right_rotate_layout = QtWidgets.QHBoxLayout()
        self.create_command_button("Right Rotate Outwards", lambda: self.main_controller.pico_controller.set_servo_rotate_right(1), right_rotate_layout)
        self.create_command_button("Right Rotate Inwards", lambda: self.main_controller.pico_controller.set_servo_rotate_right(2), right_rotate_layout)
        self.create_command_button("Right Rotate Deposit", lambda: self.main_controller.pico_controller.set_servo_rotate_right(3), right_rotate_layout)
        self.create_command_button("Right Rotate Mid", lambda: self.main_controller.pico_controller.set_servo_rotate_right(4), right_rotate_layout)
        right_rotate_group.setLayout(right_rotate_layout)
        main_layout.addWidget(right_rotate_group)

        left_grip_group = QtWidgets.QGroupBox()
        left_grip_layout = QtWidgets.QHBoxLayout()
        self.create_command_button("Left Grip Closed", lambda: self.main_controller.pico_controller.set_grip_left(1), left_grip_layout)
        self.create_command_button("Left Grip Open", lambda: self.main_controller.pico_controller.set_grip_left(2), left_grip_layout)
        left_grip_group.setLayout(left_grip_layout)
        main_layout.addWidget(left_grip_group)

        left_rotate_group = QtWidgets.QGroupBox()
        left_rotate_layout = QtWidgets.QHBoxLayout()
        self.create_command_button("Left Rotate Outwards", lambda: self.main_controller.pico_controller.set_servo_rotate_left(1), left_rotate_layout)
        self.create_command_button("Left Rotate Inwards", lambda: self.main_controller.pico_controller.set_servo_rotate_left(2), left_rotate_layout)
        self.create_command_button("Left Rotate Deposit", lambda: self.main_controller.pico_controller.set_servo_rotate_left(3), left_rotate_layout)
        self.create_command_button("Left Rotate Mid", lambda: self.main_controller.pico_controller.set_servo_rotate_left(4), left_rotate_layout)
        left_rotate_group.setLayout(left_rotate_layout)
        main_layout.addWidget(left_rotate_group)

        system_group = QtWidgets.QGroupBox()
        system_layout = QtWidgets.QHBoxLayout()
        home_btn = self.create_command_button("Home Everything", lambda: self.main_controller.pico_controller.home_pico(), system_layout)
        home_btn.setStyleSheet("font-size: 20px; background-color: #85c1e9; border-radius: 10px; padding: 10px;")
        emergency_btn = self.create_command_button("EMERGENCY STOP", lambda: self.main_controller.pico_controller.emergency_stop(), system_layout)
        emergency_btn.setStyleSheet("font-size: 20px; background-color: #e74c3c; color: white; border-radius: 10px; padding: 10px;")
        system_group.setLayout(system_layout)
        main_layout.addWidget(system_group)

        back_btn = QtWidgets.QPushButton("Back to Main Menu")
        back_btn.setFixedHeight(60)
        back_btn.setStyleSheet("font-size: 24px; background-color: #ff4444; border-radius: 10px;")
        back_btn.clicked.connect(lambda: window.stacked.setCurrentIndex(1))
        main_layout.addWidget(back_btn)

        self.setLayout(main_layout)

    # Stepper control callbacks
    def step_mid_up(self):
        self.mid_stepper_value += 250
        self.main_controller.pico_controller.set_command('b', self.mid_stepper_value)

    def step_mid_down(self):
        self.mid_stepper_value = max(0, self.mid_stepper_value - 250)
        self.main_controller.pico_controller.set_command('b', self.mid_stepper_value)

    def step_right_up(self):
        self.right_stepper_value += 50
        self.main_controller.pico_controller.set_command('a', self.right_stepper_value)

    def step_right_down(self):
        self.right_stepper_value = max(0, self.right_stepper_value - 50)
        self.main_controller.pico_controller.set_command('a', self.right_stepper_value)

    def create_command_button(self, text, command_func, layout):
        btn = QtWidgets.QPushButton(text)
        btn.setFixedHeight(60)
        btn.setStyleSheet("font-size: 16px; border-radius: 10px; background-color: #f0f0f0;")
        btn.clicked.connect(command_func)
        layout.addWidget(btn)
        return btn

    def add_close_and_stop_buttons(self, layout, stop_callback):
        button_layout = QtWidgets.QHBoxLayout()
        stop_btn = QtWidgets.QPushButton("STOP")
        stop_btn.setFixedSize(100, 40)
        stop_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        stop_btn.clicked.connect(stop_callback)
        close_btn = QtWidgets.QPushButton("X")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        close_btn.clicked.connect(QtWidgets.QApplication.quit)
        button_layout.addWidget(stop_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def stop_everything(self):
        self.main_controller.pico_controller.set_command('e', 0)  # stop all pico actions
        self.async_runner.run_task(self.main_controller.motor_controller.set_stop())
        time.sleep(1)
        os.system("pkill python3")


class DriveScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Main = main()
        General = general()

        self.points = 0
        self.robot_running = False
        self.initUI()
        self.points_visible = False
        
    def initUI(self):
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.addStretch()
        
        # Back button (gray)
        back_btn = QtWidgets.QPushButton("Zurück")
        back_btn.setFixedSize(60, 40)
        back_btn.setStyleSheet("font-size: 16px; background-color: #cccccc; border: none; border-radius: 5px;")
        back_btn.clicked.connect(self.go_back)
        top_bar.addWidget(back_btn)
        
        # Close button (red)
        close_btn = QtWidgets.QPushButton("X")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        close_btn.clicked.connect(QtWidgets.QApplication.quit)
        top_bar.addWidget(close_btn)
        
        main_layout.addLayout(top_bar)
        
        # Add stretch before content to push it down (vertical centering)
        main_layout.addStretch(1)
        
        # Main content area (STOP button and points display)
        content_layout = QtWidgets.QHBoxLayout()
        
        # Left side - STOP button (taking half the screen)
        stop_btn = QtWidgets.QPushButton("STOP")
        stop_btn.setMinimumHeight(300)
        stop_btn.setStyleSheet("font-size: 32px; font-weight: bold; background-color: #ff6666; border: none; border-radius: 10px;")
        stop_btn.clicked.connect(self.stop_everything)
        content_layout.addWidget(stop_btn, 1)  # 1 = stretch factor (50% of space)
        
        # Right side - Points display
        points_container = QtWidgets.QWidget()
        points_layout = QtWidgets.QVBoxLayout(points_container)
        points_layout.setContentsMargins(0, 0, 0, 0)
        
        self.value_label = QtWidgets.QLabel("Waiting for pullcord...")
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 40px;")
        
        self.points_label = QtWidgets.QLabel("0")
        self.points_label.setAlignment(QtCore.Qt.AlignCenter)
        self.points_label.setStyleSheet("font-size: 80px; font-weight: bold;")
        self.points_label.hide()
        
        points_layout.addWidget(self.value_label)
        points_layout.addWidget(self.points_label)
        points_layout.setAlignment(QtCore.Qt.AlignCenter)
        
        content_layout.addWidget(points_container, 1)  # 1 = stretch factor (50% of space)
        
        main_layout.addLayout(content_layout)
        
        # Add stretch after content to push it up (vertical centering)
        main_layout.addStretch(1)
        
        self.setLayout(main_layout)
        
    def go_back(self):
        self.main_controller.pico_controller.set_command('h', 0)  # stop all pico actions
        self.async_runner.run_task(self.main_controller.motor_controller.set_stop())
        subprocess.Popen(
            ['lxterminal', '-e', '/home/eurobot/Desktop/restart-gui.sh'],
            env=os.environ.copy()
        )

    def stop_everything(self):
        pass
        # self.main_controller.pico_controller.set_command('e', 0)  # stop all pico actions
        # self.async_runner.run_task(self.main_controller.motor_controller.set_stop())
        # time.sleep(1)
        # os.system("pkill python3")
        
    def show_points(self):
        self.value_label.setText("Points")
        self.points_label.show()
        self.points_visible = True
        self.value_label.setStyleSheet("font-size: 60px; font-weight: bold;")
        
    # def start_robot(self):
    #     if not self.robot_running:
    #         self.robot_running = True
    #         self.async_runner.run_task(self.run_robot_controller())
            
    # def stop_robot(self):
    #     self.robot_running = False
        
    # async def run_robot_controller(self):
    #     self.main_controller.start()
    #     while True: 
    #         points = await controller.run()
    #         if points == -1: break
            
    #         self.points = points
                
    #         # Update points display logic
    #         if self.points_visible:
    #             QtCore.QMetaObject.invokeMethod(
    #                 self.points_label, "setText", 
    #                 QtCore.Qt.QueuedConnection,
    #                 QtCore.Q_ARG(str, str(self.points))
    #             )

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.General = general()

        self.setup_complete = False
        self.initUI()
        self.showFullScreen()

        self.homingComplete = False

        self.timer.start(50)
        
    def initUI(self):
        self.stacked = QtWidgets.QStackedWidget()
        self.main_scene = MainScene(self.main_controller, self.async_runner)
        self.debug_scene = DebugScene(self.main_controller, self.async_runner)
        self.drive_scene = DriveScene(self.main_controller, self.async_runner)
        self.testcodes_scene = TestCodesScene(self.main_controller, self.async_runner)
        self.picocodes_scene = PicoScene(self.main_controller, self.async_runner)
        
        self.stacked.addWidget(self.main_scene)
        self.stacked.addWidget(self.debug_scene)
        self.stacked.addWidget(self.drive_scene)
        self.stacked.addWidget(self.testcodes_scene)
        self.stacked.addWidget(self.picocodes_scene)
        self.setCentralWidget(self.stacked)
        self.main_scene.debug_btn.clicked.connect(lambda: self.stacked.setCurrentIndex(1))
        self.main_scene.start_btn.clicked.connect(self.show_waiting_screen)
        
    def show_waiting_screen(self):
        self.stacked.setCurrentIndex(2)
        self.drive_scene.setStyleSheet("background-color: white;")
        
        self.drive_scene.value_label.setText("Homing in progress...")
        self.drive_scene.value_label.setStyleSheet("font-size: 40px;")

        positions = {
            (220, 122, 84, 84) : 1, #yellow
            (507, 2, 84, 84) : 2,
            (665, 290, 84, 84) : 3,
            (250, 290, 84, 84) : 4, #blue
            (405, 2, 84, 84) : 5,
            (695, 125, 84, 84) : 6
        }
        selected_position = self.main_scene.selected_position
        selected_tactic = self.main_scene.selected_tactic
        self.main_controller.set_tactic(positions[selected_position], selected_tactic)
        # self.main_controller.pico_controller.set_command('h', 0)
        self.async_runner.run_task(self.main_controller.home())
        
        
        time.sleep(2)
        QTimer.singleShot(2000, self._switch_to_pullcord)
        

    def _switch_to_pullcord(self):
        self.drive_scene.value_label.setText("Waiting for pullcord...")
        self.setup_complete = True
        
        
    def return_to_main(self):
        self.drive_scene.stop_robot()
        self.stacked.setCurrentIndex(0)
        self.drive_scene.points_label.hide()
        self.drive_scene.value_label.setText("Waiting for pullcord...")
        self.drive_scene.value_label.setStyleSheet("font-size: 40px;")
        self.General.pullcord_pulled = False

# Positionsangaben für das Spielfeld
yellow_positions = [
    (220, 122, 84, 84),
    (507, 2, 84, 84),
    (665, 290, 84, 84)
]
blue_positions = [
    (250, 290, 84, 84),
    (405, 2, 84, 84),
    (695, 125, 84, 84)
]

if __name__ == '__main__':
    
    # Start PyQt application
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    # Clean up on exit
    result = app.exec_()
    sys.exit(result)