import sys
import os
import subprocess
import RPi.GPIO as GPIO
from PyQt5 import QtWidgets, QtCore, QtGui
import random
from main import RobotController
import asyncio
import threading
import time

# pin
pullcord = 22

# Create a global event loop for the asyncio tasks
event_loop = None
thread = None

def run_async_task(task):
    """Helper function to run async tasks in the existing event loop"""
    if event_loop is not None:
        return asyncio.run_coroutine_threadsafe(task, event_loop)
    else:
        print("Event loop not initialized!")
        return None

class AsyncRunner:
    """Manages the asyncio event loop in a separate thread"""
    def __init__(self):
        self.loop = None
        self.thread = None
        self.running = False
        
    def start(self):
        def run_event_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.running = True
            self.loop.run_forever()
        
        if not self.running:
            self.thread = threading.Thread(target=run_event_loop, daemon=True)
            self.thread.start()
            # Wait a moment for the loop to start
            time.sleep(0.1)
    
    def stop(self):
        if self.running and self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=1.0)
            self.running = False
    
    def run_task(self, coro):
        if self.running and self.loop:
            return asyncio.run_coroutine_threadsafe(coro, self.loop)
        return None

class MainScene(QtWidgets.QWidget):
    def __init__(self, main_controller: RobotController, async_runner: AsyncRunner):
        super().__init__()
        self.selected_color = None
        self.selected_position : int | None = None
        self.selected_tactic = None
        self.pullcord_active = False
        
        self.main_controller = main_controller
        self.async_runner = async_runner
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pullcord, GPIO.IN, pull_up_down=GPIO.PUD_UP)
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
    def __init__(self, main_controller: RobotController, async_runner: AsyncRunner):
        super().__init__()
        self.robot_data = {'x': 0.0, 'y': 0.0, 'angle': 0.0, 'goal_x': 100.0, 'goal_y': 200.0}
        self.main_controller = main_controller
        self.async_runner = async_runner
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.add_close_and_stop_buttons(layout, self.stop_everything)

        btns = [
            ("Shutdown", self.on_shutdown),
            ("Test Codes", self.on_test_codes),
            ("Pico Codes", self.on_pico_codes),
            ("Show Keyboard", self.on_show_keyboard),
            ("Clean Wheels", self.on_clean_wheels),
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
            ['lxterminal', '-e', f'python3 /home/eurobot/main-bot/raspi/camera_window.py'],
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
    def __init__(self, main_controller: RobotController, async_runner: AsyncRunner):
        super().__init__()
        self.main_controller = main_controller
        self.async_runner = async_runner
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)

        self.add_close_and_stop_buttons(layout, self.stop_everything)

        for text, action in [
            ("Drive 100 →", lambda: self.main_controller.motor_controller.drive_distance(1000)),
            ("Drive 100 ←", lambda: self.main_controller.motor_controller.drive_distance(-1000)),
            ("Turn 90°", lambda: self.main_controller.motor_controller.turn_angle(90)),
            ("Turn -90°", lambda: self.main_controller.motor_controller.turn_angle(-90))
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
    def __init__(self, main_controller: RobotController, async_runner: AsyncRunner):
        super().__init__()
        self.main_controller = main_controller
        self.async_runner = async_runner
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)

        self.add_close_and_stop_buttons(layout, self.stop_everything)

        for text, action in [
            ("Button 1", lambda: None),
            ("Button 2", lambda: None),
            ("Button 3", lambda: None),
            ("Button 4", lambda: None),
            ("Button 5", lambda: None)
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

class DriveScene(QtWidgets.QWidget):
    def __init__(self, main_controller: RobotController, async_runner: AsyncRunner):
        super().__init__()
        self.main_controller = main_controller
        self.async_runner = async_runner
        self.points = 0
        self.robot_running = False
        self.initUI()
        self.points_visible = False
        
    def initUI(self):
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Top bar with close button
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.addStretch()
        
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
        
    def stop_everything(self):
        self.main_controller.pico_controller.set_command('e', 0)  # stop all pico actions
        self.async_runner.run_task(self.main_controller.motor_controller.set_stop())
        time.sleep(1)
        os.system("pkill python3")
    
    def show_points(self):
        self.value_label.setText("Points")
        self.points_label.show()
        self.points_visible = True
        self.value_label.setStyleSheet("font-size: 60px; font-weight: bold;")
        
    def start_robot(self):
        if not self.robot_running:
            self.robot_running = True
            self.async_runner.run_task(self.run_robot_controller())
            
    def stop_robot(self):
        self.robot_running = False
        
    async def run_robot_controller(self):
        """Run the robot controller asynchronously"""
        await self.main_controller.start()
        
        while self.robot_running:
            try:
                not_done, self.points = await self.main_controller.run()
                if not not_done:
                    self.robot_running = False
                    break
                    
                # self.points = 0
                # Update points display logic
                if self.points_visible:
                    QtCore.QMetaObject.invokeMethod(
                        self.points_label, "setText", 
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, str(self.points))
                    )
            except Exception as e:
                print(f"Error in robot controller: {e}")
                self.robot_running = False
                break

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, main_controller: RobotController, async_runner: AsyncRunner):
        super().__init__()
        self.main_controller = main_controller
        self.async_runner = async_runner
        self.setup_complete = False
        self.initUI()
        self.showFullScreen()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_pullcord)

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

    def update_pullcord(self):
        if GPIO.input(pullcord) == GPIO.HIGH and not self.main_scene.pullcord_active and self.setup_complete:
            self.main_scene.pullcord_active = True
            self.drive_scene.show_points()
            self.drive_scene.start_robot()

    def show_waiting_screen(self):
        self.setup_complete = True
        self.stacked.setCurrentIndex(2)
        self.drive_scene.setStyleSheet("background-color: white;")
        selected_position = self.main_scene.selected_position
        selected_tactic = self.main_scene.selected_tactic
        positions = {
            (220, 122, 84, 84) : 1, #yellow
            (507, 2, 84, 84) : 2,
            (665, 290, 84, 84) : 3,
            (250, 290, 84, 84) : 4, #blue
            (405, 2, 84, 84) : 5,
            (695, 125, 84, 84) : 6
        }
        self.main_controller.set_tactic(positions[selected_position], selected_tactic)

    def return_to_main(self):
        self.drive_scene.stop_robot()
        self.stacked.setCurrentIndex(0)
        self.drive_scene.points_label.hide()
        self.drive_scene.value_label.setText("Waiting for pullcord...")
        self.drive_scene.value_label.setStyleSheet("font-size: 40px;")
        self.main_scene.pullcord_active = False

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
    # Initialize the asyncio runner in a separate thread
    async_runner = AsyncRunner()
    async_runner.start()
    
    # Initialize robot controller
    controller = RobotController()
    
    # Start PyQt application
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(controller, async_runner)
    window.show()
    
    # Clean up on exit
    result = app.exec_()
    async_runner.stop()
    sys.exit(result)