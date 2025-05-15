import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
import socket
import threading

HOST = '127.0.0.1'
PORT = 5001

class general:
    def __init__(self):
        self.pullcord_pulled = False

        self.start_server()
        threading.Thread(target=self.receive_messages, daemon=True).start()

        
    ## ! ggf umschreiben dass es im terminal minimiert aufgeht
    def start_server(self):
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                pass
        except:
            subprocess.Popen(["python3", "main.py"])

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
                print(f"Fehler beim Empfangen von Nachrichten: {e}")

class SimpleGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Daten Sender")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Button 1
        self.button_d1 = QPushButton("Send D1")
        self.button_d1.clicked.connect(self.send_d1)
        layout.addWidget(self.button_d1)

        # Button 2
        self.button_t1 = QPushButton("Send T1")
        self.button_t1.clicked.connect(self.send_t1)
        layout.addWidget(self.button_t1)

        # Button 3
        self.button_p4 = QPushButton("Send P4")
        self.button_p4.clicked.connect(self.send_p4)
        layout.addWidget(self.button_p4)

        self.setLayout(layout)

    def send_d1(self):
        # Deine Implementierung hier
        print("send_d1 aufgerufen")

    def send_t1(self):
        # Deine Implementierung hier
        print("send_t1 aufgerufen")

    def send_p4(self):
        # Deine Implementierung hier
        print("send_p4 aufgerufen")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = SimpleGUI()
    gui.show()
    sys.exit(app.exec())
