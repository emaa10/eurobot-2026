import RPi.GPIO as GPIO
import asyncio
from time import time
import logging
import socket
import threading
import sys

HOST = '127.0.0.1'
PORT = 5001


while True:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server läuft auf {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            with conn:
                print(f"Verbunden mit {addr}")
                try:
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break
                        msg = data.decode().strip()
                        print(f"Empfangen: {msg}")
                except Exception as e:
                    print(f"Fehler: {e}")