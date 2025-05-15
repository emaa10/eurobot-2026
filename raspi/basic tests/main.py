import socket
import threading
import sys
import time

HOST = '127.0.0.1'
PORT = 5001

client_socket = None  # Global client socket reference

def start_server():
    global client_socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        print(f"Server running on {HOST}:{PORT}")
        
        # Start input listener thread
        input_thread = threading.Thread(target=terminal_input_handler, daemon=True)
        input_thread.start()
        
        while True:
            client_socket, address = server_socket.accept()
            print(f"Connected to client at {address}")
            client_handler = threading.Thread(
                target=get_commands,
                args=(client_socket, address),
                daemon=True
            )
            client_handler.start()
    except KeyboardInterrupt:
        print("Server shutting down...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server_socket.close()
        print("Server stopped")

def terminal_input_handler():
    global client_socket
    
    while True:
        user_input = input("Enter message to send: ")
        if user_input.lower() == 'exit':
            print("Exiting input handler...")
            break
            
        if client_socket is not None:
            send_message(client_socket, user_input)
        else:
            print("No client connected. Wait for connection.")
        
        time.sleep(0.1)

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