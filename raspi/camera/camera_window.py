#!/usr/bin/env python3
from picamera2 import Picamera2, Preview
import time

# Kamera-Objekt initialisieren
picam2 = Picamera2()

# Preview-Fenster starten (QtGL nutzt GPU-Acceleration)
# x,y: Position, width/height: Fenstergröße in Pixel
picam2.start_preview(Preview.QTGL, x=100, y=100, width=1280, height=960)

# Kamera im Preview-Modus konfigurieren
config = picam2.create_preview_configuration({"size": (1280, 960)})
picam2.configure(config)

# Stream starten
picam2.start()
try:
    # Laufzeit (hier 60 Sekunden), oder beliebige andere Logik
    time.sleep(60)
finally:
    # Preview- und Kamera-Verbindung sauber beenden
    picam2.stop_preview()
    picam2.close()
