"""Endstop-Test: sendet ES und zeigt Pin-Zustand live. Strg+C zum Beenden."""
import serial, time, sys

PORT = '/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'

try:
    s = serial.Serial(PORT, 115200, timeout=0.1)
except Exception as e:
    print(f"Serial-Fehler: {e}")
    sys.exit(1)

time.sleep(1.0)
s.reset_input_buffer()

print("Endstop-Monitor aktiv. Drücke den Endstop und beobachte den Zustand.")
print("Strg+C zum Beenden.\n")

last = None
try:
    while True:
        s.write(b'ES\n')
        time.sleep(0.1)
        line = s.readline().decode(errors='ignore').strip()
        if line and line != last:
            last = line
            print(f"{time.strftime('%H:%M:%S')}  {line}")
        elif not line:
            pass
except KeyboardInterrupt:
    print("\nBeendet.")
finally:
    s.close()
