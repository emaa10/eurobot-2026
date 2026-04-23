#!/usr/bin/env python3
"""
Eurobot 2026 – Systemstatus

Prüft alle Hardware-Komponenten ohne sie zu initialisieren.
Kein Schreiben, kein Bewegen – nur lesen und anzeigen.

Aufruf: python3 raspi/status.py
"""

import os
import json
import glob
import subprocess
import sys

# ── Farben ────────────────────────────────────────────────────────────────
OK   = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'
WARN = '\033[93m!\033[0m'
INFO = '\033[96m·\033[0m'

def ok(msg):   print(f"  {OK}  {msg}")
def fail(msg): print(f"  {FAIL}  {msg}")
def warn(msg): print(f"  {WARN}  {msg}")
def info(msg): print(f"  {INFO}  {msg}")


# ── Hilfsfunktionen ───────────────────────────────────────────────────────

def serial_exists(pattern: str) -> str | None:
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def gpio_read(pin: int) -> int | None:
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        val = GPIO.input(pin)
        GPIO.cleanup()
        return val
    except Exception:
        return None


def systemd_status(service: str) -> str:
    try:
        r = subprocess.run(['systemctl', 'is-active', service],
                           capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return 'unknown'


# ── Checks ────────────────────────────────────────────────────────────────

def check_esp32():
    print("\n[ESP32 – Stepper-Controller]")
    port = serial_exists('/dev/serial/by-id/usb-Silicon_Labs_CP2102*')
    if port:
        ok(f"Port gefunden: {port}")
    else:
        fail("CP2102 nicht gefunden  →  USB-Kabel prüfen")


def check_servos():
    print("\n[STServo – 8 Greifer-Servos]")
    port = serial_exists('/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083062*')
    if port:
        ok(f"Port gefunden: {port}")
    else:
        fail("CH340 Servo-Adapter nicht gefunden  →  USB-Kabel prüfen")


def check_lidar():
    print("\n[Lidar]")
    port = serial_exists('/dev/serial/by-id/usb-Silicon_Labs_CP210*') or \
           serial_exists('/dev/serial/by-id/usb-*idar*') or \
           serial_exists('/dev/serial/by-id/usb-*LIDAR*')
    if port:
        ok(f"Port gefunden: {port}")
    else:
        warn("Kein Lidar-Port gefunden (optional)")


def check_camera():
    print("\n[Kamera]")
    try:
        from picamera2 import Picamera2
        cams = Picamera2.global_camera_info()
        if cams:
            ok(f"Kamera erkannt: {cams[0].get('Model', '?')}")
        else:
            fail("Keine Kamera gefunden  →  CSI-Kabel prüfen")
    except ImportError:
        warn("picamera2 nicht installiert")
    except Exception as e:
        fail(f"Kamera-Fehler: {e}")


def check_gpio():
    print("\n[GPIO – Raspi]")
    team = gpio_read(17)
    if team is None:
        fail("GPIO nicht lesbar (RPi.GPIO fehlt?)")
        return
    team_str = "Blau (LOW)" if team == 0 else "Gelb (HIGH)"
    ok(f"GPIO 17 (Team-Schalter): {team_str}")

    cord = gpio_read(22)
    cord_str = "Schnur drin (LOW)" if cord == 0 else "Schnur gezogen! (HIGH)"
    state = ok if cord == 0 else warn
    state(f"GPIO 22 (Zugschnur):   {cord_str}")


def check_config():
    print("\n[Taktik-Konfiguration]")
    cfg_path = os.path.join(os.path.dirname(__file__), 'tactic.json')
    if not os.path.exists(cfg_path):
        warn(f"tactic.json fehlt  →  Taktik 1, Pos 1 wird als Default verwendet")
        return
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
        ok(f"tactic.json: Taktik {cfg.get('tactic', '?')}, Startpos {cfg.get('start_pos', '?')}")
    except Exception as e:
        fail(f"tactic.json ungültig: {e}")


def check_service():
    print("\n[systemd Service]")
    status = systemd_status('eurobot.service')
    if status == 'active':
        ok(f"eurobot.service: {status}")
    elif status == 'inactive':
        info(f"eurobot.service: {status}  (manuell starten: sudo systemctl start eurobot)")
    else:
        warn(f"eurobot.service: {status}")


def check_log():
    print("\n[Letzter Log-Eintrag]")
    log_path = '/home/eurobot/eurobot-2026/raspi/eurobot.log'
    if not os.path.exists(log_path):
        info("Noch kein Log vorhanden")
        return
    try:
        lines = open(log_path).readlines()
        last = [l.rstrip() for l in lines[-5:] if l.strip()]
        for l in last:
            info(l)
    except Exception:
        warn("Log nicht lesbar")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("══════════════════════════════════════")
    print("  Eurobot 2026 – Systemstatus")
    print("══════════════════════════════════════")

    check_esp32()
    check_servos()
    check_lidar()
    check_camera()
    check_gpio()
    check_config()
    check_service()
    check_log()

    print("\n══════════════════════════════════════\n")


if __name__ == '__main__':
    main()
