import sys
import os
import socket
import threading
import time
import logging
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QStackedWidget, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QMessageBox, QSpacerItem, QSizePolicy, QScrollArea
)
from PyQt5.QtGui import QPixmap, QColor, QBrush, QFont
from PyQt5.QtCore import Qt, QRectF, QTimer

HOST = '127.0.0.1'
PORT = 5001

class Communication(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.pullcord_pulled = False
        self.homing_1_done = False
        self.homing_2_done = False
        self.points = 0
        self.connected = False
        self.socket = None
        self.lock = threading.Lock()
        logging.basicConfig(filename='/home/eurobot/main-bot/raspi/eurobot.log', level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.start_server()
        self.start()

    def l(self, msg: str):
        print(msg)
        self.logger.info("GUI - " + msg)

    def start_server(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((HOST, PORT))
            s.close()
            self.l("Debug: Server already running.")
        except:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            main_path = os.path.join(script_dir, 'main.py')
            subprocess.Popen(['lxterminal', '-e', f'python3 {main_path}'], cwd=script_dir)
            self.l("Debug: Started main.py in new terminal.")
            time.sleep(1)
        self.connect()

    def connect(self):
        if self.connected:
            return
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((HOST, PORT))
            self.connected = True
            self.l("Debug: Connected to server.")
        except Exception as e:
            self.l(f"Debug: Connection error: {e}")
            self.connected = False

    def send_command(self, msg):
        with self.lock:
            if not self.connected:
                self.connect()
                if not self.connected:
                    self.l("Debug: Cannot send - not connected.")
                    return False
            try:
                self.socket.sendall(msg.encode())
                self.l(f"Debug: Sent: {msg}")
                return True
            except Exception as e:
                self.l(f"Debug: Send error: {e}")
                self.connected = False
                return False

    def run(self):
        while True:
            if not self.connected:
                self.connect()
                time.sleep(0.5)
                continue
            try:
                data = self.socket.recv(1024).decode()
                if not data:
                    self.connected = False
                    continue
                self.l(f"Debug: Received raw: {data}")
                ### receive here ###
                cmd = data[0]
                if cmd == 'p':
                    self.pullcord_pulled = True
                    self.l("Debug: pullcord pulled event detected.")
                elif cmd == 'h':
                    if not self.homing_1_done:
                        self.homing_1_done = True
                        self.l("Debug: homing stage 1 done.")
                    else:
                        self.homing_2_done = True
                        self.l("Debug: homing stage 2 done.")
                elif cmd == 'c':
                    # c<points>
                    if data[1:].isdigit():
                        self.points = int(data[1:])
                        self.l(f"Debug: Updated points to {self.points}.")
                else:
                    self.l(f"Debug: Unknown command: {data}")
            except Exception as e:
                self.l(f"Debug: Receive error: {e}")
                self.connected = False
                time.sleep(1)

class MainWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.comm = Communication()
        self.selected_rect_id = None
        self.selected_tactic = None
        self.color = None
        self.game_state = 0
        self.init_ui()

    def init_ui(self):
        self.stack = QStackedWidget(self)
        self.init_start_screen()      # Index 0
        self.init_game_screen()       # Index 1
        self.init_debug_menu()        # Index 2
        self.init_test_screen()       # Index 3
        self.init_servo_screen()      # Index 4
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        self.setLayout(layout)
        self.showFullScreen()
        self.setWindowState(Qt.WindowFullScreen)

    def init_start_screen(self):
        w = QWidget(); v = QVBoxLayout(w)
        hdr = QHBoxLayout(); hdr.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        close_btn = QPushButton('✕'); close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet('background: transparent; font-size:18px;')
        hdr.addWidget(close_btn); v.addLayout(hdr)
        hb = QHBoxLayout()
        for name, col in [('Gelb', '#FFD600'), ('Blau', '#2979FF')]:
            btn = QPushButton(name)
            btn.setStyleSheet(f'background: {col}; color: #fff; padding: 10px; border-radius: 8px')
            btn.clicked.connect(lambda _, c=col: self.select_color(c))
            hb.addWidget(btn)
        v.addLayout(hb)
        self.view = QGraphicsView(); self.scene = QGraphicsScene()
        pix = QPixmap('/home/eurobot/main-bot/raspi/eurobot.png').scaled(480, 180, Qt.KeepAspectRatioByExpanding)
        self.scene.addPixmap(pix); self.view.setScene(self.scene); v.addWidget(self.view)
        self.rect_items = {col: [] for col in ['#FFD600', '#2979FF']}
        # indexes: https://bergerhq.de/eurobot-index
        coords = {'#FFD600': [(405, 145), (160, 245), (27, 7)],
                  '#2979FF': [(380, 7), (250, 245), (10, 150)]}
        rect_c = 1
        for col, pts in coords.items():
            for (x, y) in pts:
                r = QGraphicsRectItem(QRectF(x, y, 72,72))
                r.setBrush(QBrush(QColor(col).lighter(150)))
                r.setFlags(QGraphicsRectItem.ItemIsSelectable | QGraphicsRectItem.ItemIsMovable)
                r.rect_id = rect_c; r.color = col
                self.rect_items[col].append(r); self.scene.addItem(r)
                rect_c += 1
        hb2 = QHBoxLayout()
        for i in range(1, 5):
            b = QPushButton(f'Tactic {i}'); b.clicked.connect(lambda _, x=i: self.select_tactic(x)); hb2.addWidget(b)
        v.addLayout(hb2)
        hb3 = QHBoxLayout()
        for txt, fn in [('START', self.start_game),
                        ('DEBUG', lambda: self.stack.setCurrentIndex(2)),
                        ('STOP', lambda: self.comm.send_command('es'))]:
            b = QPushButton(txt); b.clicked.connect(fn); hb3.addWidget(b)
        v.addLayout(hb3); w.setLayout(v); self.stack.addWidget(w)

    def select_color(self, col):
        self.color = col
        for items in self.rect_items.values():
            for item in items:
                item.setVisible(item.color == col)
        self.comm.l(f"Debug: Selected color {col}.")

    def select_tactic(self, t): self.comm.l(f"Debug: Selected tactic {t}."); self.selected_tactic = t

    def start_game(self):
        items = [i for i in self.rect_items.get(self.color, []) if i.isSelected()]
        if not items or not self.selected_tactic:
            QMessageBox.warning(self, 'Warn', 'Select start pos and tactic'); return
        cmd = f'st{items[0].rect_id};{self.selected_tactic}'
        self.comm.l(cmd)
        self.comm.send_command(cmd); self.comm.l(f"Debug: Game started with command {cmd}.")
        self.stack.setCurrentIndex(1); self.game_state = 1
        self.timer = QTimer(self); self.timer.timeout.connect(self.update_game); self.timer.start(100)

    def update_game(self):
        if self.game_state == 1:
            # Start Homing 1
            self.game_state = 4
            font = QFont()
            font.setPointSize(45)
            self.game_label.setFont(font)
            self.game_label.setText('Homing...')
            self.comm.l("Debug: Homing 1 started.")
            # self.comm.send_command("hb") # home bot
        
        elif self.game_state == 2 and self.comm.homing_1_done:
            # Ask if user wants to continue
            self.game_state = 3
            self.timer.stop()
            resp = QMessageBox.question(self, 'Continue?', 'Do you want to continue?', QMessageBox.Yes | QMessageBox.No)
            self.comm.l(f"Debug: Continue response {resp}.")
            if resp == QMessageBox.Yes:
                self.game_label.setText('Homing 2...')
                self.comm.send_command('hb') #! home bot
                self.comm.l("Debug: Sent homing 2 continue.")
                self.game_state = 4
                self.timer.start(100)
            else:
                self.close()
                return
        
        elif self.game_state == 4 and self.comm.homing_1_done:
            # Homing 2 done
            self.game_state = 5
            font = QFont()
            font.setPointSize(45)
            self.game_label.setFont(font)
            self.game_label.setText("Waiting for pullcord...")
            self.comm.l("Debug: Homing #2 done, waiting for pullcord.")
        
        elif self.game_state == 5 and self.comm.pullcord_pulled:
            # Game starts after pullcrod pulled
            self.game_state = 6
            font = QFont()
            font.setPointSize(45)
            self.game_label.setFont(font)
            self.game_label.setText(f'Points: {self.comm.points}')
            self.comm.l(f"Debug: Final points displayed {self.comm.points}.")

            # Live points update
            self.points_timer = QTimer(self)
            self.points_timer.timeout.connect(self.update_points_label)
            self.points_timer.start(200)

    def update_points_label(self):
        self.game_label.setText(f'Points: {self.comm.points}')

    def init_game_screen(self):
        w = QWidget()
        v = QVBoxLayout(w)

        # Header mit Zurück- und Schließen-Button
        hdr = QHBoxLayout()
        back_btn = QPushButton('←')
        back_btn.setFixedSize(30, 30)
        back_btn.setStyleSheet('background: transparent; font-size:18px;')
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        hdr.addWidget(back_btn)

        hdr.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        close_btn = QPushButton('✕')
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet('background: transparent; font-size:18px;')
        close_btn.clicked.connect(self.close)
        hdr.addWidget(close_btn)
        v.addLayout(hdr)

        self.game_label = QLabel('Waiting for pullcord.')
        self.game_label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.game_label)
        w.setLayout(v)
        self.stack.addWidget(w)

    def init_debug_menu(self):
        w = QWidget()
        v = QVBoxLayout(w)

        # Header mit Close-Button
        hdr = QHBoxLayout()
        back_btn = QPushButton('←')
        back_btn.setFixedSize(30, 30)
        back_btn.setStyleSheet('background: transparent; font-size:18px;')
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        hdr.addWidget(back_btn)

        hdr.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        close_btn = QPushButton('✕')
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet('background: transparent; font-size:18px;')
        hdr.addWidget(close_btn)
        v.addLayout(hdr)

        # Liste von Debug-Aktionen
        actions = [
            ('Shutdown', 'sudo shutdown now'),
            ('Reboot', 'sudo reboot'),
            ('Testcodes', 'test_dummy'),
            ('Pico Codes', 'pico_dummy'),
            ('Clean Wheels', 'c'),
            ('Show Camera', 'camera'),
            ('Log Tail', 'logtail')
        ]

        for title, command in actions:
            btn = QPushButton(title)
            btn.clicked.connect(lambda _, x=command: self.run_debug(x))
            v.addWidget(btn)

        # EMERGENCY STOP Knopf
        est = QPushButton('EMERGENCY STOP')
        est.clicked.connect(lambda: self.comm.send_command('es'))
        v.addWidget(est)

        w.setLayout(v)
        self.stack.addWidget(w)

    def run_debug(self, cmd):
        if cmd == 'test_dummy': self.stack.setCurrentIndex(3)
        elif cmd == 'pico_dummy': self.stack.setCurrentIndex(4)
        elif cmd == 'c': self.comm.send_command('cw'); self.comm.l("Debug: Sent clean wheels command.")
        elif cmd == 'camera': subprocess.Popen(['lxterminal', '-e', 'python3 /home/eurobot/main-bot/raspi/camera/camera_window.py'])
        elif cmd == 'logtail': subprocess.Popen(['lxterminal', '-e', 'tail -f /home/eurobot/main-bot/raspi/eurobot.log'])
        else: subprocess.call(cmd.split())

    def init_test_screen(self):
        w = QWidget()
        w.setMaximumSize(800, 480)  # Feste maximale Größe
        main_layout = QVBoxLayout(w)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Header mit Zurück- und Schließen-Button
        hdr = QHBoxLayout()
        back_btn = QPushButton('←')
        back_btn.setFixedSize(25, 25)
        back_btn.setStyleSheet('background: transparent; font-size:14px;')
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        hdr.addWidget(back_btn)

        hdr.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        close_btn = QPushButton('✕')
        close_btn.setFixedSize(25, 25)
        close_btn.setStyleSheet('background: transparent; font-size:14px;')
        close_btn.clicked.connect(self.close)
        hdr.addWidget(close_btn)
        main_layout.addLayout(hdr)

        # Scroll Area für Test Buttons
        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_widget = QWidget()
        v = QVBoxLayout(scroll_widget)
        v.setSpacing(2)

        # Test Code Buttons
        title = QLabel('Test Codes')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 14px; font-weight: bold; margin: 5px;')
        title.setMaximumHeight(25)
        v.addWidget(title)

        test_commands = [
            ('Drive 100cm', 'dd1000'),
            ('Turn 90 right', 'ta90'),
            ('Turn 180 right', 'ta180'),
            ('Stepper home', 'sh'),
            ('Cans anfahren', 'ac'),
            ('Cans greifen', 'gc'),
            ('Home gripper', 'hg'),
            ('Home bot', 'hb')
        ]

        for btn_text, command in test_commands:
            btn = QPushButton(btn_text)
            btn.setFixedHeight(35)
            btn.setStyleSheet('padding: 5px; margin: 1px; font-size: 12px; border: 1px solid #ccc;')
            btn.clicked.connect(lambda _, cmd=command: self.send_test_command(cmd))
            v.addWidget(btn)

        # Emergency Stop
        est_btn = QPushButton('EMERGENCY STOP')
        est_btn.setFixedHeight(40)
        est_btn.setStyleSheet('background: red; color: white; padding: 5px; margin: 5px; font-size: 12px; font-weight: bold;')
        est_btn.clicked.connect(lambda: self.comm.send_command('es'))
        v.addWidget(est_btn)

        scroll_widget.setLayout(v)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        w.setLayout(main_layout)
        self.stack.addWidget(w)

    def send_test_command(self, cmd):
        self.comm.send_command(cmd)
        self.comm.l(f"Debug: Sent test command: {cmd}")

    def init_servo_screen(self):
        w = QWidget()
        w.setMaximumSize(800, 480)  # Feste maximale Größe
        main_layout = QVBoxLayout(w)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Header mit Zurück- und Schließen-Button
        hdr = QHBoxLayout()
        back_btn = QPushButton('←')
        back_btn.setFixedSize(25, 25)
        back_btn.setStyleSheet('background: transparent; font-size:14px;')
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        hdr.addWidget(back_btn)

        hdr.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        close_btn = QPushButton('✕')
        close_btn.setFixedSize(25, 25)
        close_btn.setStyleSheet('background: transparent; font-size:14px;')
        close_btn.clicked.connect(self.close)
        hdr.addWidget(close_btn)
        main_layout.addLayout(hdr)

        # Scroll Area für alle Servo-Buttons
        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_widget = QWidget()
        v = QVBoxLayout(scroll_widget)
        v.setSpacing(1)

        # Title
        title = QLabel('Servo Controls')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 14px; font-weight: bold; margin: 5px;')
        title.setMaximumHeight(25)
        v.addWidget(title)

        # Servo Commands - basierend on den gegebenen Funktionen
        servo_groups = [
            {
                'name': 'Mitte Lift',
                'commands': [
                    ('Lift unten', 'ws3;2900'),
                    ('Lift oben', 'ws3;3030')
                ]
            },
            {
                'name': 'Mitte Grip',
                'commands': [
                    ('Grip auf', 'ws7;3700'),
                    ('Grip zu', 'ws7;3200')
                ]
            },
            {
                'name': 'Right Rotate',
                'commands': [
                    ('R außen', 'ws11;3825'),
                    ('R mitte', 'ws11;3040'),
                    ('R innen', 'ws11;2500'),
                ]
            },
            {
                'name': 'Plate Rotate',
                'commands': [
                    ('Plate oben', 'ws9;1800'),
                    ('Plate unten', 'ws9;2800')
                ]
            },
            {
                'name': 'Right Grip',
                'commands': [
                    ('R Grip auf', 'ws1;3950'),
                    ('R Grip zu', 'ws1;3450')
                ]
            },
            {
                'name': 'Left Grip',
                'commands': [
                    ('L Grip auf', 'ws2;150'),
                    ('L Grip zu', 'ws2;630')
                ]
            },
            {
                'name': 'Left Rotate',
                'commands': [
                    ('L außen', 'ws10;180'),
                    ('L mitte', 'ws10;975'),
                    ('L innen', 'ws10,1540')
                ]
            },
            {
                'name': 'Plate Grip',
                'commands': [
                    ('Pl. Grip auf', 'ws8;950'),
                    ('Pl. Grip zu', 'ws8;1640')
                ]
            },
            {
                'name': 'Flag',
                'commands': [
                    ('Flag o', 'ws6;2200'),
                    ('Flag u', 'ws6;750')
                ]
            }
        ]

        for group in servo_groups:
            # Group Label
            group_label = QLabel(group['name'])
            group_label.setStyleSheet('font-size: 13px; font-weight: bold; margin-top: 8px; margin-bottom: 2px; color: #333;')
            group_label.setMaximumHeight(20)
            # v.addWidget(group_label)

            # Group Buttons in einer Reihe wenn möglich
            if len(group['commands']) <= 3:
                hbox = QHBoxLayout()
                hbox.setSpacing(2)
                for button_text, command in group['commands']:
                    btn = QPushButton(button_text)
                    btn.setFixedHeight(28)
                    btn.setStyleSheet('padding: 3px; margin: 1px; font-size: 10px; background: #f8f8f8; border: 1px solid #ddd;')
                    btn.clicked.connect(lambda _, cmd=command: self.send_servo_command(cmd))
                    hbox.addWidget(btn)
                v.addLayout(hbox)
            else:
                # Mehr als 2 Buttons vertikal
                for button_text, command in group['commands']:
                    btn = QPushButton(button_text)
                    btn.setFixedHeight(28)
                    btn.setStyleSheet('padding: 3px; margin: 1px; font-size: 10px; background: #f8f8f8; border: 1px solid #ddd;')
                    btn.clicked.connect(lambda _, cmd=command: self.send_servo_command(cmd))
                    v.addWidget(btn)

        # Emergency Stop
        est_btn = QPushButton('EMERGENCY STOP')
        est_btn.setFixedHeight(45)
        est_btn.setStyleSheet('background: red; color: white; padding: 5px; margin: 8px; font-size: 11px; font-weight: bold;')
        est_btn.clicked.connect(lambda: self.comm.send_command('es'))
        v.addWidget(est_btn)

        scroll_widget.setLayout(v)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        w.setLayout(main_layout)
        self.stack.addWidget(w)

    def send_servo_command(self, cmd):
        self.comm.send_command(cmd)
        self.comm.l(f"Debug: Sent servo command: {cmd}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DisableWindowContextHelpButton, True)
    mw = MainWindow()
    mw.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
    mw.showFullScreen()
    sys.exit(app.exec_())