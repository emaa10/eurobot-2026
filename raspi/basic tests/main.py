import socket
import threading
import sys
import time

HOST = '127.0.0.1'
PORT = 5001

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        print(f"Server running on {HOST}:{PORT}")
        
        while True:
            client_socket, address = server_socket.accept()
            print(f"Connected to client at {address}")

            get_commands(client_socket, address)
            # client_handler = threading.Thread(
            #     target=get_commands,
            #     args=(client_socket, address),
            #     daemon=True
            # )
            # client_handler.start()
    except KeyboardInterrupt:
        print("Server shutting down...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server_socket.close()
        print("Server stopped")

def get_commands(client_socket, address):
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                print(f"Client {address} disconnected")
                break
                
            message = data.decode().strip()
            print(f"Received from {address}: {message}")

            cmd = message[0]
            if cmd == "t":
                startpos = int(message[1:message.index(",")])
                tactic = int(message[message.index(",")+1:])
                print(f"Tactic set: Startpos: {startpos} - tactic: {tactic}")
            elif cmd == "p":
                pcmd = message[1:]
                print(f"pico command: {pcmd}")
            elif cmd == "d":
                dist = int(message[1:])
                print(f"drive distance: {dist}")
            elif cmd == "a":
                angle = int(message[1:])
                print(f"angle: {angle}")
            elif cmd == "e0":
                print("emergency stop")
            else:
                print(f"got shit: {message}")

                
    except Exception as e:
        print(f"Error handling client {address}: {e}")
    finally:
        client_socket.close()

# h: homing done
# p: pullcord pulled
# c<count>: set count points
def send_message(client_socket, msg: str):
    """Send a string message to the connected client"""
    try:
        client_socket.sendall(msg.encode())
        print(f"Sent to client: {msg}")
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

if __name__ == "__main__":
    start_server()