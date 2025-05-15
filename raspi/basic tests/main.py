import socket
import threading
import sys

HOST = '127.0.0.1'
PORT = 5001

def start_server():
    """Start the server with proper socket handling"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)  # Allow up to 5 pending connections
        print(f"Server running on {HOST}:{PORT}")
        
        # Accept and handle clients
        while True:
            client_socket, address = server_socket.accept()
            print(f"Connected to client at {address}")
            
            # Create a new thread to handle this client
            client_handler = threading.Thread(
                target=handle_client,
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

def handle_client(client_socket, address):
    """Handle communication with a specific client"""
    try:
        while True:
            # Receive data from client
            data = client_socket.recv(1024)
            if not data:
                print(f"Client {address} disconnected")
                break
                
            message = data.decode().strip()
            print(f"Received from {address}: {message}")
            
            # Process the message and send back responses if needed
            # For example, you might want to respond to specific commands:
            if message == "p4":
                # Send "p1" back as a response
                response = "p1"
                client_socket.sendall(response.encode())
                print(f"Sent to {address}: {response}")
                
    except Exception as e:
        print(f"Error handling client {address}: {e}")
    finally:
        client_socket.close()

if __name__ == "__main__":
    start_server()