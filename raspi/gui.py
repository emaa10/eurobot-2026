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
PORT = 5002
#! sdfjlk

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
            #! subprocess.Popen(['lxterminal', '-e', f'python3 {main_path}'], cwd=script_dir)
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
        # self.init_test_screen()       # Index 3
        # self.init_servo_screen()      # Index 4
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
        cmd = f'st{items[0].rect_id},{self.selected_tactic}'
        self.comm.l(cmd)
        self.comm.send_command(cmd); self.comm.l(f"Debug: Game started with command {cmd}.")
        self.stack.setCurrentIndex(1); self.game_state = 1
        self.timer = QTimer(self); self.timer.timeout.connect(self.update_game); self.timer.start(100)

    def update_game(self):
        if self.game_state == 1:
            # Start Homing 1
            self.game_state = 2
            self.game_label.setText('Homing 1...')
            self.comm.l("Debug: Homing 1 started.")
            self.comm.send_command("hg") # home gripper
        
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
        
        elif self.game_state == 4 and self.comm.homing_2_done:
            # Homing 2 done
            self.game_state = 5
            self.game_label.setText("Waiting for pullcord...")
            self.comm.l("Debug: Homing #2 done, waiting for pullcord.")
        
        elif self.game_state == 5 and self.comm.pullcord_pulled:
            # Game starts after pullcrod pulled
            self.game_state = 6
            font = QFont()
            font.setPointSize(32)
            self.game_label.setFont(font)
            self.game_label.setText(f'Punkte: {self.comm.points}')
            self.comm.l(f"Debug: Final points displayed {self.comm.points}.")

            # Live points update
            self.points_timer = QTimer(self)
            self.points_timer.timeout.connect(self.update_points_label)
            self.points_timer.start(200)

    def update_points_label(self):
        self.game_label.setText(f'Punkte: {self.comm.points}')

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

        hdr.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

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
        v = QVBoxLayout(w)

        # Header mit Zurück- und Schließen-Button
        hdr = QHBoxLayout()
        back_btn = QPushButton('←')
        back_btn.setFixedSize(30, 30)
        back_btn.setStyleSheet('background: transparent; font-size:18px;')
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(2))  # Zurück zu Debug
        hdr.addWidget(back_btn)

        hdr.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        close_btn = QPushButton('✕')
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet('background: transparent; font-size:18px;')
        close_btn.clicked.connect(self.close)
        hdr.addWidget(close_btn)
        v.addLayout(hdr)

        # Test Code Buttons
        title = QLabel('Test Codes')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 18px; font-weight: bold; margin: 10px;')
        v.addWidget(title)

        test_commands = [
            ('Drive 100cm →', 'dd100'),
            ('Turn 90 right →', 'ta90'),
            ('Turn 180 right →', 'ta180'),
            ('Stepper home →', 'sh'),
            ('Cans anfahren →', 'ac'),
            ('Cans greifen →', 'gc'),
            ('Home gripper →', 'hg'),
            ('Home bot →', 'hb')
        ]

        for title, command in test_commands:
            btn = QPushButton(title)
            btn.setStyleSheet('padding: 10px; margin: 2px; font-size: 14px;')
            btn.clicked.connect(lambda _, cmd=command: self.send_test_command(cmd))
            v.addWidget(btn)

        # Emergency Stop
        est_btn = QPushButton('EMERGENCY STOP')
        est_btn.setStyleSheet('background: red; color: white; padding: 15px; margin: 10px; font-size: 16px; font-weight: bold;')
        est_btn.clicked.connect(lambda: self.comm.send_command('es'))
        v.addWidget(est_btn)

        w.setLayout(v)
        self.stack.addWidget(w)

    def send_test_command(self, cmd):
        self.comm.send_command(cmd)
        self.comm.l(f"Debug: Sent test command: {cmd}")

    def init_servo_screen(self):
        w = QWidget()
        main_layout = QVBoxLayout(w)

        # Header mit Zurück- und Schließen-Button
        hdr = QHBoxLayout()
        back_btn = QPushButton('←')
        back_btn.setFixedSize(30, 30)
        back_btn.setStyleSheet('background: transparent; font-size:18px;')
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(2))  # Zurück zu Debug
        hdr.addWidget(back_btn)

        hdr.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        close_btn = QPushButton('✕')
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet('background: transparent; font-size:18px;')
        close_btn.clicked.connect(self.close)
        hdr.addWidget(close_btn)
        main_layout.addLayout(hdr)

        # Scroll Area für alle Servo-Buttons
        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_widget = QWidget()
        v = QVBoxLayout(scroll_widget)

        # Title
        title = QLabel('Servo Controls')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 18px; font-weight: bold; margin: 10px;')
        v.addWidget(title)

        # Servo Commands - basierend auf den gegebenen Funktionen
        servo_groups = [
            {
                'name': 'Servo Mitte Lift',
                'commands': [
                    ('Servo mitte lift oben', 'ws3;4000'),
                    ('Servo mitte lift unten', 'ws3;3900')
                ]
            },
            {
                'name': 'Servo Mitte Grip',
                'commands': [
                    ('Servo mitte grip auf', 'ws7;3550'),
                    ('Servo mitte grip zu', 'ws7;3250')
                ]
            },
            {
                'name': 'Servo Right Rotate',
                'commands': [
                    ('Servo right rotate außen', 'ws11;3825'),
                    ('Servo right rotate mitte', 'ws11;2900'),
                    ('Servo right rotate innen', 'ws11;2500')
                ]
            },
            {
                'name': 'Servo Plate Rotate',
                'commands': [
                    ('Servo plate rotate oben', 'ws9;1800'),
                    ('Servo plate rotate unten', 'ws9;2800')
                ]
            },
            {
                'name': 'Servo Right Grip',
                'commands': [
                    ('Servo right grip auf', 'ws1;800'),
                    ('Servo right grip zu', 'ws1;380')
                ]
            },
            {
                'name': 'Servo Left Grip',
                'commands': [
                    ('Servo left grip auf', 'ws2;100'),
                    ('Servo left grip zu', 'ws2;640')
                ]
            },
            {
                'name': 'Servo Left Rotate',
                'commands': [
                    ('Servo left rotate außen', 'ws10;600'),
                    ('Servo left rotate mitte', 'ws10;1450'),
                    ('Servo left rotate innen', 'ws10;1950')
                ]
            },
            {
                'name': 'Servo Plate Grip',
                'commands': [
                    ('Servo plate grip auf', 'ws8;1000'),
                    ('Servo plate grip zu', 'ws8;1550')
                ]
            }
        ]

        for group in servo_groups:
            # Group Label
            group_label = QLabel(group['name'])
            group_label.setStyleSheet('font-size: 16px; font-weight: bold; margin-top: 15px; margin-bottom: 5px; color: #333;')
            v.addWidget(group_label)

            # Group Buttons
            for button_text, command in group['commands']:
                btn = QPushButton(button_text)
                btn.setStyleSheet('padding: 8px; margin: 2px; font-size: 12px; background: #f0f0f0; border: 1px solid #ccc;')
                btn.clicked.connect(lambda _, cmd=command: self.send_servo_command(cmd))
                v.addWidget(btn)

        # Emergency Stop
        est_btn = QPushButton('EMERGENCY STOP')
        est_btn.setStyleSheet('background: red; color: white; padding: 15px; margin: 10px; font-size: 16px; font-weight: bold;')
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