import sys
import os
import subprocess
from PyQt5 import QtWidgets, QtCore, QtGui
import random

class MainScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.selected_color = None
        self.selected_position = None
        self.selected_tactic = None
        self.pullcord_active = False

    def initUI(self):
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # Color Selection
        color_layout = QtWidgets.QHBoxLayout()
        self.color_group = QtWidgets.QButtonGroup()
        
        self.yellow_btn = QtWidgets.QPushButton("GELB")
        self.yellow_btn.setFixedSize(250, 80)
        self.yellow_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffff00;
                font-size: 28px;
                border: 3px solid black;
                border-radius: 10px;
            }
            QPushButton:checked {
                border: 5px solid #00ff00;
            }
        """)
        self.yellow_btn.setCheckable(True)
        
        self.blue_btn = QtWidgets.QPushButton("BLAU")
        self.blue_btn.setFixedSize(250, 80)
        self.blue_btn.setStyleSheet("""
            QPushButton {
                background-color: #0000ff;
                color: white;
                font-size: 28px;
                border: 3px solid black;
                border-radius: 10px;
            }
            QPushButton:checked {
                border: 5px solid #00ff00;
            }
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

        # Spielfeld Container als QLabel
        self.field_container = QtWidgets.QLabel()
        self.field_container.setFixedSize(1000, 400)
        self.field_container.setStyleSheet("""
            background-color: #ffffff;
            border: 3px solid black;
        """)
        self.field_container.setAlignment(QtCore.Qt.AlignCenter)

        # Bild laden und skalieren
        image_path = os.path.expanduser("/home/pi/main-bot/raspi/eurobot.png")
        if os.path.exists(image_path):
            pixmap = QtGui.QPixmap(image_path)
            pixmap = pixmap.scaled(
                980,  # 1000 - 2*10 border
                380,  # 400 - 2*10 border
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            self.field_container.setPixmap(pixmap)
            self.field_container.setScaledContents(False)

        self.position_buttons = []
        self.layout.addWidget(self.field_container, alignment=QtCore.Qt.AlignCenter)

        # Taktik Buttons
        tactics_layout = QtWidgets.QHBoxLayout()
        self.tactic_buttons = []
        for i in range(4):
            btn = QtWidgets.QPushButton(f"TAKTIK {i+1}")
            btn.setFixedSize(280, 60)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 20px;
                    background-color: #f0f0f0;
                }
                QPushButton:checked {
                    background-color: white;
                    border: 2px solid black;
                }
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, x=i+1: self.on_tactic_selected(x))
            self.tactic_buttons.append(btn)
            tactics_layout.addWidget(btn)
        self.layout.addLayout(tactics_layout)

        # Start/Debug Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("START")
        self.start_btn.setFixedHeight(60)
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet("""
            QPushButton {
                font-size: 28px;
                background-color: #808080;
                color: white;
                border-radius: 10px;
            }
            QPushButton:enabled {
                background-color: #00ff00;
                color: black;
            }
        """)
        
        self.debug_btn = QtWidgets.QPushButton("DEBUG")
        self.debug_btn.setFixedHeight(60)
        self.debug_btn.setStyleSheet("font-size: 28px; border-radius: 10px;")
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.debug_btn)
        self.layout.addLayout(button_layout)

        self.setLayout(self.layout)

        # Statuszeile unten
        status_bar = QtWidgets.QHBoxLayout()
        self.lbl_pullcord = QtWidgets.QLabel("Pullcord: NICHT AKTIV")
        self.lbl_pullcord.setStyleSheet("color: red; font-weight: bold;")
        
        self.lbl_status = QtWidgets.QLabel("X: 0.0 | Y: 0.0 | Winkel: 0.0°")
        
        status_bar.addWidget(self.lbl_pullcord)
        status_bar.addStretch()
        status_bar.addWidget(self.lbl_status)
        
        self.layout.addLayout(status_bar) 

    def update_pullcord_status(self, active):
        self.pullcord_active = active
        text = "Pullcord: AKTIV" if active else "Pullcord: NICHT AKTIV"
        color = "green" if active else "red"
        self.lbl_pullcord.setText(text)
        self.lbl_pullcord.setStyleSheet(f"color: {color}; font-weight: bold;")

    def on_color_changed(self, button, checked):
        if checked:
            self.selected_color = button.text()
            positions = yellow_positions if button == self.yellow_btn else blue_positions
            self.show_position_rectangles(positions)
        self.check_selections()

    def show_position_rectangles(self, positions):
        # Alte Buttons entfernen
        for btn in self.position_buttons:
            btn.deleteLater()
        self.position_buttons.clear()
        
        # Neue Buttons erstellen
        for idx, pos in enumerate(positions):
            btn = QtWidgets.QPushButton(self.field_container)
            btn.setGeometry(QtCore.QRect(*pos))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 0, 0, 30);
                    border: 3px solid #ff0000;
                    border-radius: 5px;
                }
                QPushButton[selected="true"] {
                    background-color: rgba(0, 255, 0, 50);
                    border: 3px solid #00ff00;
                }
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

    def on_position_selected(self, position):
        self.selected_position = position
        self.check_selections()

    def on_tactic_selected(self, tactic):
        # Deselect other tactics
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
        self.initUI()
        self.robot_data = {
            'x': 0.0,
            'y': 0.0,
            'angle': 0.0,
            'goal_x': 100.0,
            'goal_y': 200.0
        }
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)

        # Status Anzeige
        status_group = QtWidgets.QGroupBox("Status")
        status_layout = QtWidgets.QGridLayout()
        
        self.lbl_position = QtWidgets.QLabel("X: 0.0 mm\nY: 0.0 mm")
        self.lbl_angle = QtWidgets.QLabel("Angle: 0.0°")
        self.lbl_goal = QtWidgets.QLabel("Goal: (0.0, 0.0)")
        
        status_layout.addWidget(QtWidgets.QLabel("Pos:"), 0, 0)
        status_layout.addWidget(self.lbl_position, 0, 1)
        status_layout.addWidget(QtWidgets.QLabel("Ausrichtung:"), 1, 0)
        status_layout.addWidget(self.lbl_angle, 1, 1)
        status_layout.addWidget(QtWidgets.QLabel("Ziel:"), 2, 0)
        status_layout.addWidget(self.lbl_goal, 2, 1)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        buttons = [
            ("Shutdown", self.on_shutdown),
            ("Test Codes", self.on_test_codes),
            ("Show Keyboard", self.on_show_keyboard),
            ("Clean Wheels", self.on_clean_wheels),
            ("Show Camera Stream", self.on_show_camera)
        ]

        for text, handler in buttons:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedHeight(80)
            btn.setStyleSheet("font-size: 24px; border-radius: 10px;")
            btn.clicked.connect(handler)
            layout.addWidget(btn)

        # Back Button
        back_btn = QtWidgets.QPushButton("Zurück")
        back_btn.setFixedHeight(60)
        back_btn.setStyleSheet("font-size: 24px; background-color: #ff4444; border-radius: 10px;")
        back_btn.clicked.connect(lambda: window.stacked.setCurrentIndex(0))
        layout.addWidget(back_btn)

        self.setLayout(layout)

    def update_data(self):
        # Dummy-Daten - später durch echte Werte ersetzen
        self.robot_data['x'] += 1
        self.robot_data['y'] += 0.5
        self.robot_data['angle'] = (self.robot_data['angle'] + 5) % 360
        
        self.lbl_position.setText(f"X: {self.robot_data['x']:.1f} mm\nY: {self.robot_data['y']:.1f} mm")
        self.lbl_angle.setText(f"Angle: {self.robot_data['angle']:.1f}°")
        self.lbl_goal.setText(f"Goal: ({self.robot_data['goal_x']:.1f}, {self.robot_data['goal_y']:.1f})")

    def on_shutdown(self):
        os.system("sudo shutdown now")

    def on_test_codes(self):
        window.stacked.setCurrentIndex(3)

    def on_show_keyboard(self):
        subprocess.Popen(['wvkbd'], env=dict(os.environ, WVKBD_HEIGHT='250'))

    def on_clean_wheels(self):
        pass  # Implement wheel cleaning logic

    def on_show_camera(self):
        pass  # Implement camera stream


class TestCodesScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)
        
        buttons = [
            ("Drive 100 →", lambda: None),
            ("Drive 100 ←", lambda: None),
            ("Turn 90°", lambda: None),
            ("Turn -90°", lambda: None)
        ]

        for text, handler in buttons:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedHeight(80)
            btn.setStyleSheet("font-size: 24px; border-radius: 10px;")
            btn.clicked.connect(handler)
            layout.addWidget(btn)

        # Back Button
        back_btn = QtWidgets.QPushButton("Zurück")
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
        
        # Stop Button
        self.stop_btn = QtWidgets.QPushButton("STOP")
        self.stop_btn.setFixedSize(120, 60)
        self.stop_btn.setStyleSheet("""
            background-color: red;
            font-size: 24px;
            color: white;
            border-radius: 10px;
        """)
        self.stop_btn.clicked.connect(lambda: os.system("killall python3"))
        layout.addWidget(self.stop_btn, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)

        # Value Display
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
        self.showMaximized()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_status)
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

        # Verbindungen
        self.main_scene.debug_btn.clicked.connect(lambda: self.stacked.setCurrentIndex(1))
        self.main_scene.start_btn.clicked.connect(self.show_waiting_screen)
        self.drive_scene.stop_btn.clicked.connect(self.return_to_main)

    def show_waiting_screen(self):
        self.stacked.setCurrentIndex(2)
        self.drive_scene.setStyleSheet("background-color: white;")

    def return_to_main(self):
        self.stacked.setCurrentIndex(0)
        self.drive_scene.points_label.hide()
        self.drive_scene.value_label.setText("Waiting for pullcord...")
        self.drive_scene.value_label.setStyleSheet("font-size: 40px;")
    
    def update_status(self):
        # Dummy-Daten für die Hauptseite
        status_text = f"X: {random.uniform(0,3000):.1f} mm | "
        status_text += f"Y: {random.uniform(0,2000):.1f} mm | "
        status_text += f"Winkel: {random.uniform(0,360):.1f}°"
        self.main_scene.lbl_status.setText(status_text)
    
    def activate_pullcord(self):
        self.drive_scene.show_points()
        self.main_scene.update_pullcord_status(True)


# Positionsangaben für das Spielfeld
yellow_positions = [
    (220, 133, 84, 84),
    (507, 12, 84, 84),
    (665, 300, 84, 84)
]

blue_positions = [
    (250, 300, 84, 84),
    (405, 12, 84, 84),
    (695, 135, 84, 84)
]

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
