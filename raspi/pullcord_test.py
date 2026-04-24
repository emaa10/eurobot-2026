#!/usr/bin/env python3
"""
Pullcord Live-Test

Starten (2. SSH-Session):
    cd /home/eurobot/eurobot-2026
    python3 raspi/pullcord_test.py

Ctrl+C zum Beenden.
"""

import time
import RPi.GPIO as GPIO

PIN_PULLCORD = 22

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_PULLCORD, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Pullcord-Test läuft  (Ctrl+C zum Beenden)")
print("─" * 35)

last = None
try:
    while True:
        val = GPIO.input(PIN_PULLCORD)
        state = "DRAUSSEN (HIGH)" if val == GPIO.HIGH else "DRIN    (LOW) "
        if val != last:
            print(f"  → {state}")
            last = val
        time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
    print("\nBeendet.")
