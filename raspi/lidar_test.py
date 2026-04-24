#!/usr/bin/env python3
"""
Lidar Live-Test – zeigt Gegner-Erkennung in Echtzeit.

Starten (2. SSH-Session):
    cd /home/eurobot/eurobot-2026
    python3 raspi/lidar_test.py

Steuerung:
    Ctrl+C  → sauber beenden
"""

import math
import sys
import time
from modules.lidar import Lidar

# ── Testposition & Richtung (anpassen) ───────────────────────────────────
ROBOT_X   = 1500   # mm  (Mitte Spielfeld)
ROBOT_Y   = 1000   # mm
ROBOT_THT = 0      # °   (0 = Norden)
DIRECTION = -1     #     (+1 vorwärts, -1 rückwärts, 0 = drehen = Vollkreis)

# ── Erkennungsparameter ───────────────────────────────────────────────────
STOP_DIST = 300    # mm  30cm Stoppschwelle
CONE_DEG  = 45.0   # °   halber Kegelwinkel voraus/rückwärts
MIN_DIST  = 70     # mm  Eigenkörper-Radius ignorieren
MIN_HITS  = 3      # Punkte für sicheren Treffer

# ── ANSI-Farben ───────────────────────────────────────────────────────────
RED    = '\033[91m'
GREEN  = '\033[92m'
YELLOW = '\033[93m'
CYAN   = '\033[96m'
RESET  = '\033[0m'
BOLD   = '\033[1m'


def _in_cone(angle, center_deg, half_deg):
    """True wenn angle innerhalb ±half_deg um center_deg (mod 360)."""
    diff = (angle - center_deg + 180) % 360 - 180
    return abs(diff) <= half_deg


def classify(scan, x, y, theta, direction):
    """direction=0 (drehen) → Vollkreis. +1/-1 → 45°-Kegel vorne/hinten."""
    hits = []
    for angle, distance in scan:
        if distance < MIN_DIST or distance > STOP_DIST:
            continue

        # Kegelfilter nur beim Fahren
        if direction > 0 and not _in_cone(angle, 270, CONE_DEG):
            continue
        if direction < 0 and not _in_cone(angle, 90, CONE_DEG):
            continue
        # direction == 0: kein Winkelfilter → Vollkreis

        # Arena-Check
        arena_rad = math.radians(angle + theta)
        arena_x = -distance * math.sin(arena_rad) + x
        arena_y =  distance * math.cos(arena_rad) + y
        if not (0 <= arena_x <= 3000 and 0 <= arena_y <= 2000):
            continue

        d_x = distance * math.sin(math.radians(angle))
        d_y = distance * math.cos(math.radians(angle))
        hits.append((angle, distance, d_x, d_y))

    return hits


def main():
    lidar = Lidar()
    print(f"\n{CYAN}Verbinde Lidar …{RESET}")
    if not lidar.start_scanning():
        print(f"{RED}Lidar konnte nicht gestartet werden.{RESET}")
        sys.exit(1)

    print(f"{GREEN}Lidar läuft.{RESET}  Pos=({ROBOT_X},{ROBOT_Y}) θ={ROBOT_THT}° dir={DIRECTION:+d}")
    print("─" * 55)

    last_state  = None
    scan_count  = 0
    last_fps    = time.time()

    try:
        while True:
            scan = lidar.get_latest_scan()
            if scan is None:
                time.sleep(0.01)
                continue

            scan_count += 1
            hits = classify(scan, ROBOT_X, ROBOT_Y, ROBOT_THT, DIRECTION)
            detected = len(hits) >= MIN_HITS

            now = time.time()
            fps = scan_count / (now - last_fps) if (now - last_fps) > 0 else 0

            if detected != last_state:
                # Zustandswechsel → auffällig ausgeben
                if detected:
                    print(f"\n{BOLD}{RED}▶ GEGNER ERKANNT  ({len(hits)} Punkte){RESET}")
                else:
                    print(f"{GREEN}◀ frei{RESET}")
                last_state = detected

            # Immer: kompakte Statuszeile überschreiben
            pts_str = f"{len(hits)} Treffer" if hits else "–"
            bar = (RED + "●" + RESET) if detected else (GREEN + "○" + RESET)
            print(
                f"\r  {bar}  Punkte: {len(scan):4d}  Treffer: {len(hits):2d}  "
                f"fps: {fps:4.1f}   ",
                end='', flush=True
            )

            # Wenn Gegner: Top-3 Hits ausgeben
            if detected:
                top = sorted(hits, key=lambda h: h[1])[:3]
                details = '  '.join(
                    f"[{h[0]:5.1f}° {h[1]:4.0f}mm]" for h in top
                )
                print(f"\n  {YELLOW}nächste Punkte:{RESET} {details}", end='', flush=True)

            time.sleep(0.02)

    except KeyboardInterrupt:
        print(f"\n\n{CYAN}Beende …{RESET}")
    finally:
        lidar.stop()
        print("Lidar gestoppt.")


if __name__ == '__main__':
    main()
