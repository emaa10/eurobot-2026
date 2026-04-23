# Eurobot 2026
![Roboter](images/bot.png)

Differentialantrieb mit 2 Stepper-Motoren (ESP32 + TB6600), 8 STServos (Greifer + Mechanik), RPLIDAR, PiCamera2.

---

## Schnellstart

```bash
# Status aller Hardware-Komponenten prüfen
python3 raspi/status.py

# Manuell starten (interaktives Menü)
python3 raspi/main.py

# Direkt mit Taktik und Startposition
python3 raspi/main.py 2 1        # Taktik 2, Startposition 1

# Taktik in Datei setzen (für Autostart)
nano raspi/tactic.json
```

---

## Taktik einstellen

Die Datei `raspi/tactic.json` enthält die Voreinstellung für den Autostart:

```json
{ "tactic": 1, "start_pos": 1 }
```

Beim manuellen Start per `python3 raspi/main.py` erscheint ein Menü, das die Auswahl speichert.

---

## Autostart (systemd)

Der Bot startet automatisch beim Hochfahren des Raspberry Pi.

```bash
# Service einrichten (einmalig)
sudo cp raspi/eurobot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable eurobot.service

# Steuerbefehle
sudo systemctl start eurobot      # manuell starten
sudo systemctl stop eurobot       # stoppen
sudo systemctl restart eurobot    # neu starten
sudo systemctl status eurobot     # Status anzeigen

# Logs live verfolgen
journalctl -u eurobot -f

# Autostart deaktivieren
sudo systemctl disable eurobot
```

---

## Ablauf nach dem Start

1. Team-Farbe von GPIO 17 lesen (LOW = Blau, HIGH = Gelb)
2. Taktik aus `tactic.json` oder Menü/Argument
3. Homing: Greifer-Home → Wand-Kalibrierung (Odometrie gesetzt)
4. Warten auf Zugschnur (GPIO 22, HIGH-Flanke)
5. 99-Sekunden-Timer startet, Taktik läuft
6. Fertig – ESP32 stoppt

---

## Task-Aktionen (Kurzübersicht)

Vollständige Doku: [`raspi/ACTIONS.md`](raspi/ACTIONS.md)

| Kürzel | Bedeutung |
|---|---|
| `dd{mm}` | Fahre mm vorwärts/rückwärts |
| `ta{deg}` | Drehe relativ (+ = Uhrzeigersinn) |
| `tt{deg}` | Drehe auf absoluten Winkel |
| `dp{x};{y}[;θ]` | Fahre zu Koordinate (Blau-KS) |
| `sp{x};{y};{θ}` | Odometrie manuell setzen |
| `hm` | Autonomes Wand-Homing |
| `hg` | Greifer-Home |
| `gr` / `go` | Alle Greifer zu / auf |
| `gi` / `ga` | Innen / außen Greifer zu |
| `ws{id};{pos}` | Einzelnen Servo setzen (Debug) |
| `ip{n}` | +n Punkte |
| `ic` | Punkte via Kamera zählen |
| `es` | Notfall-Stopp |

---

## ESP32 flashen

```bash
cd ESP
pio run -t upload          # Port wird automatisch erkannt
pio device monitor         # Seriellen Monitor öffnen
```

---

## Dateistruktur

```
ESP/                       ESP32 PlatformIO-Projekt (Stepper-Controller)
raspi/
  main.py                  Hauptprogramm (autonom)
  status.py                Hardware-Status-Check
  client.py                SSH-Remote (optional, Debug)
  tactic.json              Aktive Taktik / Startposition
  ACTIONS.md               Vollständige Aktions-Dokumentation
  eurobot.service          systemd-Unit-File
  eurobot.log              Laufzeit-Log
  modules/
    esp32.py               Serielle Kommunikation ESP32
    servos.py              STServo USB-Bus (8 Servos)
    gripper.py             Greifer-Sequenzen
    task.py                Aktions-Dispatcher
    lidar.py               RPLIDAR
    camera.py              PiCamera2 / ArUco
    STservo_sdk/           Waveshare/Feetech STS-Protokoll
PINOUT.md                  Vollständiges Hardware-Pinout
```

---

## Hardware

| Komponente | Verbindung |
|---|---|
| ESP32 (CP2102) | USB → `/dev/serial/by-id/usb-Silicon_Labs_CP2102_...-if00` |
| STServo Adapter (CH340) | USB → `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083062-if00` |
| 2× TB6600 Stepper-Treiber | PUL+/DIR+ an ESP32 GPIO 25/26 (links), 32/33 (rechts) |
| 4× Frontgreifer (STServo) | Bus-IDs 2, 1, 11, 9 (links → rechts) |
| 2× Heben/Senken | Bus-IDs TODO |
| 2× Thermometer | Bus-IDs TODO |
| Zugschnur | GPIO 22 (Pull-Up) |
| Team-Schalter | GPIO 17 (Pull-Up, LOW=Blau) |
