import sys
import os
import subprocess
import random
from PyQt5 import QtWidgets, QtCore, QtGui

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
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Color Selection - kompakter gestaltet
        color_layout = QtWidgets.QHBoxLayout()
        self.color_group = QtWidgets.QButtonGroup()
        
        self.yellow_btn = QtWidgets.QPushButton("GELB")
        self.yellow_btn.setFixedSize(200, 60)  # Kleiner gemacht
        self.yellow_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffff00;
                font-size: 20px;
                border: 2px solid black;
                border-radius: 8px;
            }
            QPushButton:checked {
                border: 3px solid #00ff00;
            }
        """)
        self.yellow_btn.setCheckable(True)
        
        self.blue_btn = QtWidgets.QPushButton("BLAU")
        self.blue_btn.setFixedSize(200, 60)  # Kleiner gemacht
        self.blue_btn.setStyleSheet("""
            QPushButton {
                background-color: #0000ff;
                color: white;
                font-size: 20px;
                border: 2px solid black;
                border-radius: 8px;
            }
            QPushButton:checked {
                border: 3px solid #00ff00;
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

        # Spielfeld Container - kleiner für 720p
        self.field_container = QtWidgets.QLabel()
        self.field_container.setFixedSize(900, 350)  # Verkleinert
        self.field_container.setStyleSheet("""
            background-color: #ffffff;
            border: 2px solid black;
        """)
        self.field_container.setAlignment(QtCore.Qt.AlignCenter)

        # Bild laden und skalieren
        image_path = os.path.expanduser("/home/pi/main-bot/raspi/eurobot.png")
        if os.path.exists(image_path):
            pixmap = QtGui.QPixmap(image_path)
            pixmap = pixmap.scaled(
                880,  # 900 - 2*10 border
                330,  # 350 - 2*10 border
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            self.field_container.setPixmap(pixmap)
            self.field_container.setScaledContents(False)

        self.position_buttons = []
        self.layout.addWidget(self.field_container, alignment=QtCore.Qt.AlignCenter)

        # Taktik Buttons - kompakter
        tactics_layout = QtWidgets.QHBoxLayout()
        self.tactic_buttons = []
        for i in range(4):
            btn = QtWidgets.QPushButton(f"T{i+1}")
            btn.setFixedSize(150, 50)  # Kleiner und kürzere Beschriftung
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
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

        # Start/Debug Buttons - kompakter
        button_layout = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("START")
        self.start_btn.setFixedHeight(50)
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet("""
            QPushButton {
                font-size: 20px;
                background-color: #808080;
                color: white;
                border-radius: 8px;
            }
            QPushButton:enabled {
                background-color: #00ff00;
                color: black;
            }
        """)
        
        self.debug_btn = QtWidgets.QPushButton("DEBUG")
        self.debug_btn.setFixedHeight(50)
        self.debug_btn.setStyleSheet("font-size: 20px; border-radius: 8px;")
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.debug_btn)
        self.layout.addLayout(button_layout)

        # Statuszeile - kompakter
        status_bar = QtWidgets.QHBoxLayout()
        self.lbl_pullcord = QtWidgets.QLabel("Pullcord: OFF")
        self.lbl_pullcord.setStyleSheet("color: red; font-weight: bold; font-size: 12px;")
        
        self.lbl_status = QtWidgets.QLabel("X:0.0 Y:0.0 A:0.0°")
        self.lbl_status.setStyleSheet("font-size: 12px;")
        
        status_bar.addWidget(self.lbl_pullcord)
        status_bar.addStretch()
        status_bar.addWidget(self.lbl_status)
        
        self.layout.addLayout(status_bar)

        self.setLayout(self.layout)

    def update_pullcord_status(self, active):
        self.pullcord_active = active
        text = "Pullcord: ON" if active else "Pullcord: OFF"
        color = "green" if active else "red"
        self.lbl_pullcord.setText(text)
        self.lbl_pullcord.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")

    # ... [restliche Methoden bleiben gleich] ...

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
        layout.setContentsMargins(20, 20, 20, 20)  # Weniger Margin

        # Status Anzeige - kompakter
        status_group = QtWidgets.QGroupBox("Status")
        status_layout = QtWidgets.QFormLayout()  # Kompaktere Form
        
        self.lbl_position = QtWidgets.QLabel("0.0, 0.0 mm")
        self.lbl_angle = QtWidgets.QLabel("0.0°")
        self.lbl_goal = QtWidgets.QLabel("100.0, 200.0")
        
        status_layout.addRow("Position:", self.lbl_position)
        status_layout.addRow("Winkel:", self.lbl_angle)
        status_layout.addRow("Ziel:", self.lbl_goal)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Buttons - kleiner
        buttons = [
            ("Shutdown", self.on_shutdown),
            ("Test Codes", self.on_test_codes),
            ("Keyboard", self.on_show_keyboard),  # Kürzer
            ("Clean Wheels", self.on_clean_wheels),
            ("Camera", self.on_show_camera)  # Kürzer
        ]

        for text, handler in buttons:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedHeight(60)  # Kleiner
            btn.setStyleSheet("font-size: 18px; border-radius: 8px;")  # Kleinere Schrift
            btn.clicked.connect(handler)
            layout.addWidget(btn)

        # Back Button
        back_btn = QtWidgets.QPushButton("Zurück")
        back_btn.setFixedHeight(50)
        back_btn.setStyleSheet("font-size: 18px; background-color: #ff4444; border-radius: 8px;")
        back_btn.clicked.connect(lambda: window.stacked.setCurrentIndex(0))
        layout.addWidget(back_btn)

        self.setLayout(layout)

    # ... [restliche Methoden bleiben gleich] ...

# ... [restliche Klassen bleiben gleich mit entsprechenden Größenanpassungen] ...

# Positionsangaben für das Spielfeld (angepasst an neue Größe)
yellow_positions = [
    (200, 120, 75, 75),
    (450, 10, 75, 75),
    (600, 270, 75, 75)
]

blue_positions = [
    (225, 270, 75, 75),
    (360, 10, 75, 75),
    (625, 120, 75, 75)
]

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec_())