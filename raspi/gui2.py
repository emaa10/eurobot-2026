import sys
from PyQt5 import QtWidgets, QtCore, QtGui

class MainScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.selected_color = None
        self.selected_position = None
        self.selected_tactic = None

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

        # Spielfeld Container
        self.field_container = QtWidgets.QWidget()
        self.field_container.setFixedSize(1000, 400)
        self.field_container.setStyleSheet("background-color: #cccccc; border: 2px solid black;")
        self.field_layout = QtWidgets.QVBoxLayout(self.field_container)
        self.field_layout.setContentsMargins(0, 0, 0, 0)
        
        self.position_buttons = []
        self.layout.addWidget(self.field_container, alignment=QtCore.Qt.AlignCenter)

        # Taktik Buttons
        tactics_layout = QtWidgets.QHBoxLayout()
        self.tactic_buttons = []
        for i in range(4):
            btn = QtWidgets.QPushButton(f"TAKTIK {i+1}")
            btn.setFixedSize(280, 60)
            btn.setStyleSheet("font-size: 20px;")
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
                background-color: rgba(255, 0, 0, 50);
                border: 3px solid #ff0000;
                border-radius: 5px;
            """)
            btn.clicked.connect(lambda _, p=pos: self.on_position_selected(p))
            btn.show()
            self.position_buttons.append(btn)

    def on_position_selected(self, position):
        self.selected_position = position
        self.check_selections()

    def on_tactic_selected(self, tactic):
        self.selected_tactic = tactic
        self.check_selections()

    def check_selections(self):
        enable = all([self.selected_color, self.selected_position, self.selected_tactic])
        self.start_btn.setEnabled(enable)


class DebugScene(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)
        
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

    def on_shutdown(self): pass
    def on_test_codes(self): window.stacked.setCurrentIndex(3)
    def on_show_keyboard(self): pass
    def on_clean_wheels(self): pass
    def on_show_camera(self): pass


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
        layout.addWidget(self.stop_btn, alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)

        # Value Display
        self.value_label = QtWidgets.QLabel("0")
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 80px;")
        layout.addWidget(self.value_label)

        # Points Label
        points_label = QtWidgets.QLabel("Points")
        points_label.setAlignment(QtCore.Qt.AlignCenter)
        points_label.setStyleSheet("font-size: 32px;")
        layout.addWidget(points_label)

        self.setLayout(layout)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.setFixedSize(1280, 720)

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
        self.drive_scene.setStyleSheet("background-color: #00ff00;")
        self.drive_scene.value_label.setText("Waiting for pullcord...")
        self.stacked.setCurrentIndex(2)

    def return_to_main(self):
        self.stacked.setCurrentIndex(0)
        self.drive_scene.setStyleSheet("")
        self.drive_scene.value_label.setText("0")


# Positionsbeispiele für 1000x400 Container
yellow_positions = [
    (100, 100, 150, 80),
    (400, 100, 150, 80),
    (700, 100, 150, 80)
]

blue_positions = [
    (100, 250, 150, 80),
    (400, 250, 150, 80),
    (700, 250, 150, 80)
]

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
