import sys
import os
import subprocess
from PyQt5 import QtWidgets, QtCore, QtGui
import random

# hilfe: https://chatgpt.com/share/680cd025-864c-8000-8271-5632adeeb5b3

class MainScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.selected_color = None
        self.selected_position = None
        self.selected_tactic = None
        self.pullcord_active = False
        self.initUI()

    def initUI(self):
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(6)

        # Close Button (X) for non-drive scenes
        close_layout = QtWidgets.QHBoxLayout()
        close_layout.addStretch()
        close_btn = QtWidgets.QPushButton("X")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        close_btn.clicked.connect(QtWidgets.QApplication.quit)
        close_layout.addWidget(close_btn)
        self.layout.addLayout(close_layout)

        # Color Selection
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
        self.robot_data = {'x': 0.0, 'y': 0.0, 'angle': 0.0, 'goal_x': 100.0, 'goal_y': 200.0}
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Close Button
        close_layout = QtWidgets.QHBoxLayout()
        close_layout.addStretch()
        close_btn = QtWidgets.QPushButton("X")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        close_btn.clicked.connect(QtWidgets.QApplication.quit)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

        btns = [
            ("Shutdown", self.on_shutdown),
            ("Test Codes", self.on_test_codes),
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

        back_btn = QtWidgets.QPushButton("Zurück")
        back_btn.setFixedHeight(50)
        back_btn.setStyleSheet("font-size: 20px; background-color: #ff4444; border-radius: 8px;")
        back_btn.clicked.connect(lambda: window.stacked.setCurrentIndex(0))
        layout.addWidget(back_btn)

        self.setLayout(layout)

    ###############################################################
    def on_shutdown(self): os.system("sudo shutdown now")
    def on_test_codes(self): window.stacked.setCurrentIndex(3)
    def on_show_keyboard(self): subprocess.Popen(['wvkbd'], env=dict(os.environ, WVKBD_HEIGHT='250'))
    def on_clean_wheels(self): pass
    def on_show_camera(self): pass
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
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)

        # Close Button
        close_layout = QtWidgets.QHBoxLayout()
        close_layout.addStretch()
        close_btn = QtWidgets.QPushButton("X")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("font-size: 18px; background-color: #ff6666; border: none; border-radius: 5px;")
        close_btn.clicked.connect(QtWidgets.QApplication.quit)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

        for text, handler in [
            ("Drive 100 →", lambda: None),
            # ("Drive 100 →", self.on_drive_forward),
            ("Drive 100 ←", lambda: None),
            ("Turn 90°", lambda: None),
            ("Turn -90°", lambda: None)
        ]:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedHeight(80)
            btn.setStyleSheet("font-size: 24px; border-radius: 10px;")
            btn.clicked.connect(handler)
            layout.addWidget(btn)

        back_btn = QtWidgets.QPushButton("Back")
        back_btn.setFixedHeight(60)
        back_btn.setStyleSheet("font-size: 24px; background-color: #ff4444; border-radius: 10px;")
        back_btn.clicked.connect(lambda: window.stacked.setCurrentIndex(1))
        layout.addWidget(back_btn)

        self.setLayout(layout)


class DriveScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.points_visible = False

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.stop_btn = QtWidgets.QPushButton("STOP")
        self.stop_btn.setFixedSize(120, 60)
        self.stop_btn.setStyleSheet("background-color: red; font-size: 24px; color: white; border-radius: 10px;")
        self.stop_btn.clicked.connect(lambda: os.system("killall python3"))
        layout.addWidget(self.stop_btn, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)

        self.value_label = QtWidgets.QLabel("Waiting for pullcord...")
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 40px;")
        
        self.points_label = QtWidgets.QLabel("0")
        self.points_label.setAlignment(QtCore.Qt.AlignCenter)
        self.points_label.setStyleSheet("font-size: 80px;")
        self.points_label.hide()
        
        layout.addWidget(self.value_label)
        layout.addWidget(self.points_label)

        self.setLayout(layout)
    
    def show_points(self):
        self.value_label.setText("Points")
        self.points_label.show()
        self.value_label.setStyleSheet("font-size: 60px; font-weight: bold;")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.showFullScreen()
        self.timer = QtCore.QTimer()
        # self.timer.timeout.connect(self.update_pullcord)
        # des an für pullcord
        
        self.timer.start(500)

    def initUI(self):
        self.stacked = QtWidgets.QStackedWidget()
        self.main_scene = MainScene()
        self.debug_scene = DebugScene()
        self.drive_scene = DriveScene()
        self.testcodes_scene = TestCodesScene()
        
        self.stacked.addWidget(self.main_scene)
        self.stacked.addWidget(self.debug_scene)
        self.stacked.addWidget(self.drive_scene)
        self.stacked.addWidget(self.testcodes_scene)

        self.setCentralWidget(self.stacked)
        self.main_scene.debug_btn.clicked.connect(lambda: self.stacked.setCurrentIndex(1))
        self.main_scene.start_btn.clicked.connect(self.show_waiting_screen)
        self.drive_scene.stop_btn.clicked.connect(self.return_to_main)

    def show_waiting_screen(self):
        self.stacked.setCurrentIndex(2)
        self.drive_scene.setStyleSheet("background-color: white;")
        # hier taktik start button

    def return_to_main(self):
        self.stacked.setCurrentIndex(0)
        self.drive_scene.points_label.hide()
        self.drive_scene.value_label.setText("Waiting for pullcord...")
        self.drive_scene.value_label.setStyleSheet("font-size: 40px;")
    
    def activate_pullcord(self):
        self.drive_scene.show_points()
        self.main_scene.update_pullcord_status(True)

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
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

