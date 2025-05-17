import sys
import socket
import threading
import time
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QStackedWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRectItem, QMessageBox
)
from PyQt5.QtGui import QPixmap, QColor, QBrush
from PyQt5.QtCore import Qt, QRectF

HOST = '127.0.0.1'
PORT = 5001

class Communication:
    def __init__(self):
        self.pullcord_pulled = False
        self.homing_1_done = False
        self.homing_2_done = False
        self.connected = False
        self.socket = None
        self.lock = threading.Lock()
        self.start_server()
        self.connect()
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def start_server(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))
                return
        except:
            print("Server not found - please start main.py")

    def connect(self):
        if self.connected:
            return
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((HOST, PORT))
            self.connected = True
            print("Connected to server")
        except Exception as e:
            print(f"Connection error: {e}")
            self.connected = False

    def send_command(self, msg):
        if not msg:
            return False
        with self.lock:
            if not self.connected:
                self.connect()
                if not self.connected:
                    return False
            try:
                self.socket.sendall(msg.encode())
                print(f"Sent: {msg}")
                return True
            except Exception as e:
                print(f"Send error: {e}")
                self.connected = False
                self.socket.close()
                return False

    def receive_messages(self):
        while True:
            if not self.connected:
                self.connect()
                time.sleep(0.5)
                continue
            try:
                data = self.socket.recv(1024).decode()
                if not data:
                    self.connected = False
                    self.socket.close()
                    continue
                print(f"Received: {data}")
                cmd = data[0]
                if cmd == 'p':
                    self.pullcord_pulled = True
                elif cmd == 'h':
                    if not self.homing_1_done:
                        self.homing_1_done = True
                    else:
                        self.homing_2_done = True
                elif cmd.isdigit():
                    # assume 'p<points>'
                    pass
            except Exception as e:
                print(f"Receive error: {e}")
                self.connected = False
                self.socket.close()
                time.sleep(1)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(800, 480)
        self.comm = Communication()
        self.selected_rect_id = None
        self.selected_tactic = None
        self.points = 0
        self.init_ui()

    def init_ui(self):
        self.stack = QStackedWidget(self)
        self.init_start_screen()
        self.init_game_screen()
        self.init_debug_menu()
        self.init_dummy_screens()
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)
        self.setLayout(layout)

    def init_start_screen(self):
        w = QWidget()
        v = QVBoxLayout()
        # Top colored buttons
        hb = QHBoxLayout()
        btn_yellow = QPushButton("Yellow")
        btn_yellow.setStyleSheet("background-color: yellow")
        btn_blue = QPushButton("Blue")
        btn_blue.setStyleSheet("background-color: blue")
        hb.addWidget(btn_yellow)
        hb.addWidget(btn_blue)
        v.addLayout(hb)
        # Graphics view
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        pix = QPixmap("map.png")
        self.scene.addPixmap(pix)
        # add movable rects
        for i, rect in enumerate([QRectF(50,50,40,40), QRectF(150,80,40,40)]):
            item = QGraphicsRectItem(rect)
            item.setBrush(QBrush(QColor(255,0,0,100)))
            item.setFlag(QGraphicsRectItem.ItemIsSelectable)
            item.setFlag(QGraphicsRectItem.ItemIsMovable)
            item.rect_id = i
            self.scene.addItem(item)
        self.view.setScene(self.scene)
        v.addWidget(self.view)
        # tactics buttons
        hb2 = QHBoxLayout()
        for i in range(1,5):
            b = QPushButton(f"T{i}")
            b.clicked.connect(lambda _, x=i: self.select_tactic(x))
            hb2.addWidget(b)
        v.addLayout(hb2)
        # Start & Debug
        hb3 = QHBoxLayout()
        btn_start = QPushButton("START")
        btn_start.clicked.connect(self.on_start)
        btn_dbg = QPushButton("DEBUG")
        btn_dbg.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        hb3.addWidget(btn_start)
        hb3.addWidget(btn_dbg)
        v.addLayout(hb3)
        # Emergency stop & close
        hb4 = QHBoxLayout()
        btn_estop = QPushButton("EMERGENCY STOP")
        btn_estop.clicked.connect(lambda: self.comm.send_command("e0"))
        btn_close = QPushButton("CLOSE")
        btn_close.clicked.connect(self.close)
        hb4.addWidget(btn_estop)
        hb4.addWidget(btn_close)
        v.addLayout(hb4)
        w.setLayout(v)
        self.stack.addWidget(w)

    def select_tactic(self, t):
        self.selected_tactic = t
        print(f"Selected tactic {t}")

    def on_start(self):
        items = self.scene.selectedItems()
        if not items or not self.selected_tactic:
            QMessageBox.warning(self, "Warn", "Select a start pos and tactic")
            return
        self.selected_rect_id = items[0].rect_id
        cmd = f"t{self.selected_rect_id},{self.selected_tactic}"
        self.comm.send_command(cmd)
        self.stack.setCurrentIndex(1)
        threading.Thread(target=self.game_flow, daemon=True).start()

    def init_game_screen(self):
        w = QWidget()
        v = QVBoxLayout()
        self.game_label = QLabel("Waiting for pullcord.")
        v.addWidget(self.game_label)
        hb = QHBoxLayout()
        btn_estop = QPushButton("EMERGENCY STOP")
        btn_estop.clicked.connect(lambda: self.comm.send_command("e0"))
        btn_close = QPushButton("CLOSE")
        btn_close.clicked.connect(self.close)
        hb.addWidget(btn_estop)
        hb.addWidget(btn_close)
        v.addLayout(hb)
        w.setLayout(v)
        self.stack.addWidget(w)

    def game_flow(self):
        # wait pullcord
        while not self.comm.pullcord_pulled:
            time.sleep(0.1)
        self.game_label.setText("Homing...")
        # wait homing1
        while not self.comm.homing_1_done:
            time.sleep(0.1)
        # prompt continue
        res = QMessageBox.question(self, "Continue?", "CONTINUE?", QMessageBox.Yes|QMessageBox.No)
        if res == QMessageBox.Yes:
            self.comm.send_command("h")
        # wait homing2
        while not self.comm.homing_2_done:
            time.sleep(0.1)
        # waiting points
        self.comm.pullcord_pulled = False
        self.comm.homing_1_done = False
        self.comm.homing_2_done = False
        self.game_label.setText(f"Punkte: {self.points}")
        # TODO: update points from comm

    def init_debug_menu(self):
        w = QWidget()
        v = QVBoxLayout()
        for text, cmd in [
            ("Shutdown", "sudo shutdown now"),
            ("Reboot", "sudo reboot"),
            ("Testcodes", "test_dummy"),
            ("Pico Codes", "pico_dummy"),
            ("Clean Wheels", "c"),
            ("Show Camera", "camera"),
            ("Log Tail", "logtail")
        ]:
            b = QPushButton(text)
            b.clicked.connect(lambda _, x=cmd: self.run_debug(x))
            v.addWidget(b)
        # emergency & close
        hb = QHBoxLayout()
        hb.addWidget(QPushButton("EMERGENCY STOP", clicked=lambda: self.comm.send_command("e0")))
        hb.addWidget(QPushButton("CLOSE", clicked=self.close))
        v.addLayout(hb)
        w.setLayout(v)
        self.stack.addWidget(w)

    def run_debug(self, cmd):
        if cmd == "test_dummy":
            self.stack.setCurrentIndex(3)
        elif cmd == "pico_dummy":
            self.stack.setCurrentIndex(4)
        elif cmd == "c":
            self.comm.send_command("c")
        elif cmd == "camera":
            subprocess.Popen(["lxterminal", "-e", "python3 /home/eurobot/main-bot/raspi/camera/camera_window.py"], shell=False)
        elif cmd == "logtail":
            subprocess.Popen(["lxterminal", "-e", "tail -f /home/eurobot/main-bot/raspi/eurobot.log"], shell=False)
        else:
            subprocess.call(cmd.split())

    def init_dummy_screens(self):
        # Testcodes screen
        for i in range(2):
            w = QWidget()
            v = QVBoxLayout()
            v.addWidget(QLabel(f"Dummy {i+1}"))
            for j in range(2):
                v.addWidget(QPushButton(f"Btn {j+1}"))
            v.addWidget(QPushButton("EMERGENCY STOP", clicked=lambda: self.comm.send_command("e0")))
            v.addWidget(QPushButton("CLOSE", clicked=self.close))
            w.setLayout(v)
            self.stack.addWidget(w)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec_())
