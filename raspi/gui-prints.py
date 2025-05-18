import socket
import threading
import time
import sys

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
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
                test_socket.connect((HOST, PORT))
                return  # Server is running
        except:
            print("Server nicht gefunden - bitte starte main.py")
    
    def connect(self):
        if self.connected:
            return
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((HOST, PORT))
            self.connected = True
            print("Mit Server verbunden")
        except Exception as e:
            print(f"Verbindungsfehler: {e}")
            self.connected = False
    
    # t<startpos>,<tactic>: taktik
    # p<picocommand>: pico command
    # d<distance in mm>: drive distance in mm
    # a<angle>: turn angle
    # e0: emergency stop
    def send_command(self, msg):
        if not msg:
            print("Leere Nachricht")
            return False
            
        with self.lock:
            if not self.connected:
                self.connect()
                if not self.connected:
                    print("Kann nicht senden - nicht verbunden")
                    return False
                
            try:
                self.socket.sendall(msg.encode())
                print(f"Gesendet: {msg}")
                return True
            except Exception as e:
                print(f"Sendefehler: {e}")
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
                    print("Server hat Verbindung geschlossen")
                    self.connected = False
                    self.socket.close()
                    continue
                print(f"Empfangen: {data}")

                if len(data) >= 1:
                    command = data[0]
                    
                    if command == "p":
                        self.pullcord_pulled = True
                        print("Pullcord gezogen")
                    elif command == "h":
                        if(self.homing_1_done == False):
                            self.homing_1_done = True
                            print("Homing 1 abgeschlossen")
                        else:
                            self.homing_2_done = True
                            print("Homing 2 abgeschlossen")
                    elif command == "c":
                        points = int(data[1:])
                        print(f"Punkte: {points}")
                    else:
                        print(f"Unbekannte Nachricht: {data}")
                        
            except Exception as e:
                print(f"Empfangsfehler: {e}")
                self.connected = False
                self.socket.close()
                time.sleep(1)

def print_status(comm):
    status = "Verbunden" if comm.connected else "Nicht verbunden"
    cord = "Gezogen" if comm.pullcord_pulled else "Nicht gezogen"
    homing1 = "Abgeschlossen" if comm.homing_1_done else "Nicht abgeschlossen"
    homing2 = "Abgeschlossen" if comm.homing_2_done else "Nicht abgeschlossen"
    print(f"Status: {status} | Pullcord: {cord} | Homing1: {homing1} | Homing2: {homing2}")

def print_help():
    print("\nVerfügbare Befehle:")
    print("  t<startpos>,<taktik>  - Taktik setzen (z.B. t1,2)")
    print("  p<picocommand>        - Pico-Befehl senden (z.B. ptest)")
    print("  d<distance>           - Fahrdistanz in mm (z.B. d100)")
    print("  a<angle>              - Drehwinkel (z.B. a90)")
    print("  e0                    - Notfallstopp")
    print("  status                - Aktuellen Status anzeigen")
    print("  help                  - Diese Hilfe anzeigen")
    print("  exit                  - Programm beenden")

def main():
    print("=== Kommandozeilenclient für Robotersteuerung ===")
    print("Gib 'help' ein für verfügbare Befehle.")
    
    comm = Communication()
    
    try:
        while True:
            cmd = input("\nBefehl eingeben: ")
            
            if cmd.lower() == "exit":
                print("Programm wird beendet...")
                break
            elif cmd.lower() == "help":
                print_help()
            elif cmd.lower() == "status":
                print_status(comm)
            else:
                comm.send_command(cmd)
    except KeyboardInterrupt:
        print("\nProgramm wird beendet...")
    finally:
        if comm.connected and comm.socket:
            comm.socket.close()

if __name__ == "__main__":
    main()
