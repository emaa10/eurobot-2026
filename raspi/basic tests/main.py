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
    