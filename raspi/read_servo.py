"""Liest aktuelle Position eines Servos. Aufruf: python3 read_servo.py <id>"""
import sys
import time
from modules.servos import Servos
from modules.STservo_sdk.sts import STS_TORQUE_ENABLE, STS_MODE

sid = int(sys.argv[1]) if len(sys.argv) > 1 else 8

s = Servos()
if not s.available:
    print("Servo bus nicht verfügbar")
    sys.exit(1)

# In Position-Mode bringen, kurz Torque aktivieren um sauber lesen zu können
s.packet_handler.write1ByteTxRx(sid, STS_MODE, 0)
s.packet_handler.write1ByteTxRx(sid, STS_TORQUE_ENABLE, 1)
time.sleep(0.05)

# Mehrere Versuche – ReadPos kann gelegentlich -7 zurückgeben
for i in range(5):
    pos, result, _ = s.packet_handler.ReadPos(sid)
    if result == 0:
        print(f"Servo {sid} pos: {pos}")
        break
    time.sleep(0.05)
else:
    print(f"ReadPos schlug fehl (result={result})")
    sys.exit(2)

# Torque wieder aus
s.packet_handler.write1ByteTxRx(sid, STS_TORQUE_ENABLE, 0)
print(f"Servo {sid} detached.")
