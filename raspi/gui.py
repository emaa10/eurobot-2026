import sys
import os
import socket
import threading
import time
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QStackedWidget, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QMessageBox, QSpacerItem, QSizePolicy
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
        self.points = 0
        self.connected = False
        self.socket = None
        self.lock = threading.Lock()
        self.start_server()
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def start_server(self):
        # Versuche Verbindung, sonst starte Server in neuem Terminal
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((HOST, PORT))
            s.close()
        except:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            main_path = os.path.join(script_dir, 'basic\ tests/main.py')
            try:
                subprocess.Popen(['lxterminal', '-e', f'python3 {main_path}'], cwd=script_dir)
                time.sleep(1)
            except Exception as e:
                print(f"Fehler beim Starten von main.py: {e}")
        self.connect()

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
        with self.lock:
            if not self.connected:
                self.connect()
                if not self.connected:
                    print("Cannot send - not connected")
                    return False
            try:
                self.socket.sendall(msg.encode())
                print(f"Sent: {msg}")
                return True
            except Exception as e:
                print(f"Send error: {e}")
                self.connected = False
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
                    continue
                print(f"Received: {data}")
                cmd = data[0]
                if cmd == 'p':
                    # pullcord oder Punkte
                    if data.startswith('p') and len(data) > 1 and data[1:].isdigit():
                        self.points = int(data[1:])
                    else:
                        self.pullcord_pulled = True
                elif cmd == 'h':
                    if not self.homing_1_done:
                        self.homing_1_done = True
                    else:
                        self.homing_2_done = True
            except Exception as e:
                print(f"Receive error: {e}")
                self.connected = False
                time.sleep(1)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.comm = Communication()
        self.selected_rect_id = None
        self.selected_tactic = None
        self.color = None
        self.init_ui()

    def init_ui(self):
        self.showFullScreen()
        self.stack = QStackedWidget(self)
        self.init_start_screen()
        self.init_game_screen()
        self.init_debug_menu()
        self.init_dummy_screens()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.stack)
        self.setLayout(layout)

    def init_start_screen(self):
        w = QWidget(); v = QVBoxLayout(w)
        # Header: Spacer + Close
        hdr = QHBoxLayout(); hdr.addSpacerItem(QSpacerItem(40,20,QSizePolicy.Expanding,QSizePolicy.Minimum))
        close_btn = QPushButton('✕'); close_btn.setFixedSize(30,30)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet('background: transparent; font-size:18px;')
        hdr.addWidget(close_btn)
        v.addLayout(hdr)
        # Farb-Buttons
        hb = QHBoxLayout()
        for name, col in [('Gelb','#FFD600'),('Blau','#2979FF')]:
            btn = QPushButton(name)
            btn.setStyleSheet(f'background-color: {col}; color: white; font-size:18px; padding:10px; border-radius:8px;')
            btn.clicked.connect(lambda _, c=col: self.select_color(c))
            hb.addWidget(btn)
        v.addLayout(hb)
        # Graphics View
        self.view = QGraphicsView(); self.scene = QGraphicsScene()
        pix = QPixmap('map.png').scaled(800,300,Qt.KeepAspectRatioByExpanding)
        self.scene.addPixmap(pix)
        self.rect_items = {col:[] for col in ['#FFD600','#2979FF']}
        coords = {'#FFD600':[(50,50),(150,80),(250,100)], '#2979FF':[(60,150),(160,180),(260,200)]}
        for color, points in coords.items():
            for i,(x,y) in enumerate(points):
                r = QGraphicsRectItem(QRectF(x,y,40,40))
                c = QColor(color)
                r.setBrush(QBrush(QColor(c.red(),c.green(),c.blue(),150)))
                r.setFlag(QGraphicsRectItem.ItemIsSelectable)
                r.setFlag(QGraphicsRectItem.ItemIsMovable)
                r.rect_id = i; r.color = color
                self.rect_items[color].append(r); self.scene.addItem(r)
        self.view.setScene(self.scene); v.addWidget(self.view)
        # Taktik-Buttons
        hb2 = QHBoxLayout()
        for i in range(1,5):
            b = QPushButton(f'T{i}')
            b.setStyleSheet('font-size:16px; padding:8px;')
            b.clicked.connect(lambda _, x=i: self.select_tactic(x))
            hb2.addWidget(b)
        v.addLayout(hb2)
        # Start/Debug/Estop
        hb3 = QHBoxLayout()
        for text,fn in [('START',self.on_start),('DEBUG',lambda: self.stack.setCurrentIndex(2)),('STOP',lambda: self.comm.send_command('e0'))]:
            b=QPushButton(text); b.clicked.connect(fn)
            b.setStyleSheet('font-size:16px; padding:10px; border-radius:8px;')
            hb3.addWidget(b)
        v.addLayout(hb3)
        w.setLayout(v); self.stack.addWidget(w)

    def select_color(self, col):
        self.color = col
        for c, items in self.rect_items.items():
            for itm in items: itm.setVisible(c==col)

    def select_tactic(self, t): self.selected_tactic=t

    def on_start(self):
        items=[i for i in self.rect_items.get(self.color,[]) if i.isSelected()]
        if not items or not self.selected_tactic:
            QMessageBox.warning(self,'Warn','Select start pos and tactic')
            return
        self.comm.send_command(f't{items[0].rect_id},{self.selected_tactic}')
        self.stack.setCurrentIndex(1); threading.Thread(target=self.game_flow,daemon=True).start()

    def init_game_screen(self):
        w=QWidget();v=QVBoxLayout(w)
        self.game_label=QLabel('Waiting for pullcord.'); self.game_label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.game_label)
        hdr=QHBoxLayout();hdr.addSpacerItem(QSpacerItem(40,20,QSizePolicy.Expanding,QSizePolicy.Minimum))
        btn_close=QPushButton('✕');btn_close.setFixedSize(30,30);btn_close.clicked.connect(self.close)
        btn_close.setStyleSheet('background: transparent; font-size:18px;');hdr.addWidget(btn_close);v.addLayout(hdr)
        stop=QPushButton('EMERGENCY STOP');stop.clicked.connect(lambda:self.comm.send_command('e0'))
        stop.setStyleSheet('font-size:16px; padding:10px; border-radius:8px;');v.addWidget(stop)
        w.setLayout(v);self.stack.addWidget(w)

    def game_flow(self):
        while not self.comm.pullcord_pulled: time.sleep(0.1)
        self.game_label.setText('Homing...')
        while not self.comm.homing_1_done: time.sleep(0.1)
        resp = QMessageBox.question(self,'Continue?','CONTINUE?',QMessageBox.Yes|QMessageBox.No)
        if resp == QMessageBox.Yes:
            self.comm.send_command('h')
        else:
            self.close(); return
        while not self.comm.homing_2_done: time.sleep(0.1)
        self.game_label.setText(f'Punkte: {self.comm.points}')

    def init_debug_menu(self):
        w=QWidget();v=QVBoxLayout(w)
        hdr=QHBoxLayout();hdr.addSpacerItem(QSpacerItem(40,20,QSizePolicy.Expanding,QSizePolicy.Minimum))
        btn_close=QPushButton('✕');btn_close.setFixedSize(30,30);btn_close.clicked.connect(self.close)
        btn_close.setStyleSheet('background: transparent; font-size:18px;');hdr.addWidget(btn_close);v.addLayout(hdr)
        actions=[('Shutdown','sudo shutdown now'),('Reboot','sudo reboot'),('Testcodes','test_dummy'),
                 ('Pico Codes','pico_dummy'),('Clean Wheels','c'),('Show Camera','camera'),('Log Tail','logtail')]
        for t,c in actions:
            b=QPushButton(t);b.clicked.connect(lambda _,x=c:self.run_debug(x))
            b.setStyleSheet('font-size:16px; padding:10px; border-radius:8px;');v.addWidget(b)
        est=QPushButton('EMERGENCY STOP');est.clicked.connect(lambda:self.comm.send_command('e0'))
        est.setStyleSheet('font-size:16px; padding:10px; border-radius:8px;');v.addWidget(est)
        w.setLayout(v);self.stack.addWidget(w)

    def run_debug(self,cmd):
        if cmd=='test_dummy':self.stack.setCurrentIndex(3)
        elif cmd=='pico_dummy':self.stack.setCurrentIndex(4)
        elif cmd=='c':self.comm.send_command('c')
        elif cmd=='camera':subprocess.Popen(['lxterminal','-e','python3 /home/.../camera_window.py'])
        elif cmd=='logtail':subprocess.Popen(['lxterminal','-e','tail -f /home/.../eurobot.log'])
        else:subprocess.call(cmd.split())

    def init_dummy_screens(self):
        for idx in [3,4]:
            w=QWidget();v=QVBoxLayout(w)
            lbl=QLabel(f'Dummy Screen {idx-2}');lbl.setAlignment(Qt.AlignCenter);v.addWidget(lbl)
            for j in range(2):v.addWidget(QPushButton(f'Btn {j+1}'))
            est=QPushButton('EMERGENCY STOP');est.clicked.connect(lambda:self.comm.send_command('e0'))
            est.setStyleSheet('font-size:16px; padding:10px; border-radius:8px;');v.addWidget(est)
            w.setLayout(v);self.stack.addWidget(w)

if __name__=='__main__':
    app=QApplication(sys.argv);mw=MainWindow();sys.exit(app.exec_())
