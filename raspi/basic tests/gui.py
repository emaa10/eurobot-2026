import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel
import socket
import threading
import subprocess
import time

HOST = '127.0.0.1'
PORT = 5001

class Communication:
    def __init__(self):
        self.pullcord_pulled = False
        self.connected = False
        self.socket = None
        self.lock = threading.Lock()  # For thread-safe operations
        
        # Try to start server if not running
        self.start_server()
        
        # Start a persistent connection
        self.connect()
        
        # Start receiving thread
        threading.Thread(target=self.receive_messages, daemon=True).start()
    
    def start_server(self):
        """Check if server is running, if not try to start it"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
                test_socket.connect((HOST, PORT))
                return  # Server is running
        except:
            # Uncomment to auto-start the server if needed
            # subprocess.Popen(["python3", "main.py"])
            print("Server not found - please start main.py")
    
    def connect(self):
        """Establish a persistent connection to the server"""
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
        """Send a command to the server"""
        if not msg:
            print("Empty message")
            return False
            
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
                self.socket.close()
                return False
    
    def receive_messages(self):
        """Continuously receive messages from the server"""
        while True:
            if not self.connected:
                self.connect()
                time.sleep(1)  # Avoid rapid reconnection attempts
                continue
                
            try:
                data = self.socket.recv(1024).decode()
                if not data:
                    print("Server closed connection")
                    self.connected = False
                    self.socket.close()
                    continue
                    
                print(f"Received: {data}")
                
                # Process received data
                if len(data) >= 2:
                    command = data[0]
                    value1 = int(data[1:])
                    
                    if command == "p" and value1 == 1:
                        self.pullcord_pulled = True
                    elif command == "p" and value1 == 0:
                        self.pullcord_pulled = False
                        
            except Exception as e:
                print(f"Receive error: {e}")
                self.connected = False
                self.socket.close()
                time.sleep(1)  # Avoid rapid reconnection attempts

class SimpleGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Daten Sender")
        
        # Create a single communication instance
        self.comm = Communication()
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Status label
        self.status_label = QLabel("Not connected")
        layout.addWidget(self.status_label)
        
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
        
        # Update status periodically
        self.update_timer = threading.Thread(target=self.update_status, daemon=True)
        self.update_timer.start()
        
        self.setLayout(layout)
    
    def update_status(self):
        """Update connection status display"""
        while True:
            status = "Connected" if self.comm.connected else "Not connected"
            cord = "Pulled" if self.comm.pullcord_pulled else "Not pulled"
            self.status_label.setText(f"Status: {status} | Pullcord: {cord}")
            time.sleep(0.5)
    
    def send_d1(self):
        self.comm.send_command("d1")
        print("send_d1 called")
    
    def send_t1(self):
        self.comm.send_command("t1")
        print("send_t1 called")
    
    def send_p4(self):
        self.comm.send_command("p4")
        print("send_p4 called")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = SimpleGUI()
    gui.show()
    sys.exit(app.exec())