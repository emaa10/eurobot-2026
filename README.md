# Eurobot 2026
![Roboter](images/bot.png)

Differentialantrieb mit 2 Schrittmotoren (ESP32 + TB6600), 8 STServos (Greifer, Lift, Winker), RPLIDAR A1 zur Gegnererkennung, PiCamera2 für ArUco-Erkennung.

---

## Systemübersicht

```
┌─────────────────────────────────────────────────────────┐
│                   Raspberry Pi 4                        │
│                                                         │
│  main.py (asyncio)                                      │
│  ├── TCP-Server :5001  ←── client.py (SSH)             │
│  ├── esp32.py   ──USB──► ESP32 (Schrittmotoren)        │
│  ├── servos.py  ──USB──► STServo-Adapter (8 Servos)    │
│  ├── lidar.py   ──USB──► RPLIDAR A1                    │
│  ├── camera.py  ──CSI──► PiCamera2                     │
│  └── GPIO 22 ──────────► Zugschnur                     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  ESP32 DevKit v1 (FreeRTOS, 2 Kerne)                   │
│  Core 0: stepperTask  – AccelStepper Tight-Loop        │
│  Core 1: uartTask     – Serial I/O → Command-Queue     │
│                                                         │
│  GPIO 26 STEP_R  →  TB6600 Rechts                      │
│  GPIO 27 DIR_R   →  TB6600 Rechts                      │
│  GPIO 25 DIR_L   →  TB6600 Links                       │
│  GPIO 33 STEP_L  →  TB6600 Links                       │
└─────────────────────────────────────────────────────────┘
```

---

## Hardware

### Schrittmotoren & Treiber

| Komponente | Detail |
|---|---|
| Treiber | TB6600 (×2) |
| Microstep | 16 → DIP-Schalter an TB6600 einstellen |
| Schritte/Umdrehung | 200 × 16 = **3200 steps/rev** |
| Raddurchmesser | 60 mm |
| Radabstand (Achse–Achse) | 200 mm |
| Max. Geschwindigkeit | 1500 steps/s |
| Beschleunigung | 1200 steps/s² |

TB6600 Verkabelung:
```
ESP32 GPIO26 ──► PUL+  ]  TB6600 Rechter Motor
ESP32 GPIO27 ──► DIR+  ]  (PUL-/DIR- auf GND)
ESP32 GPIO25 ──► DIR+  ]  TB6600 Linker Motor (gespiegelt montiert)
ESP32 GPIO33 ──► PUL+  ]
GND          ──► PUL-/DIR- (beide Treiber)
Motorspannung 9–42 V an VCC/GND der Treiber
```

> Linker Motor ist gespiegelt montiert → `stepperL.setPinsInverted(true)` im ESP-Code.
> Vorwärts = stepperR und stepperL beide `move(+s)`.

### STServos (Feetech STS-Protokoll, Halbduplex UART, 1 MBaud)

Alle 8 Servos auf einem Bus, gesteuert über USB-Adapter am Raspi.

| ID | Funktion | Position auf/hoch | Position zu/runter |
|---|---|---|---|
| **1** | Greifer links innen | 1500 | 2500 |
| **2** | Greifer links außen | 1048 | 2000 |
| **9** | Greifer rechts außen | 1048 | 2048 |
| **11** | Greifer rechts innen | 1048 | 2100 |
| **3** | Lift A | TODO | TODO |
| **6** | Lift B | TODO | TODO |
| **7** | Winker links | relativ +1707 steps (150°) | relativ −1707 steps |
| **8** | Winker rechts | relativ +1707 steps (150°) | relativ −1707 steps |

Greifer-Reihenfolge von links nach rechts: **ID 2 → ID 1 → ID 11 → ID 9**

> Winker verwenden relative Positionierung (ReadPos + Delta), da keine feste Ausgangsposition bekannt ist.
> Lift-Positionen (IDs 3 und 6) müssen noch kalibriert werden.

### Lidar

| Parameter | Wert |
|---|---|
| Modell | RPLIDAR A1 |
| Stoppdistanz | 400 mm (40 cm) |
| Kegelwinkel | ±60° (120° gesamt) vor/hinter dem Roboter |
| Eigenkörper-Filter | < 70 mm werden ignoriert |
| Mindesttreffer | 3 Punkte für sicheren Stopp |
| Vorwärts-Richtung | 270° (Schere = rechte Seite des Roboters) |
| Rückwärts-Richtung | 90° |
| Beim Drehen | Vollkreis (kein Kegelfilter) |

Erkannte Hindernisse werden gegen die Arena-Grenzen (0–3000 mm × 0–2000 mm) gefiltert, um Wände nicht als Hindernisse zu werten.

### GPIO (Raspberry Pi, BCM-Nummerierung)

| GPIO | Pin | Funktion | Pegel |
|---|---|---|---|
| **22** | 15 | Zugschnur | Pull-Up: LOW = drin, HIGH-Flanke = Spielstart |

### USB-Gerätepfade

```
ESP32 (CP2102):
  /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_...-if00
  → in raspi/modules/esp32.py → PORT anpassen

STServo-Adapter (CH340, Seriennr. 5A46083059):
  /dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083059-if00
  → in raspi/modules/servos.py → PORT (bereits eingetragen)

RPLIDAR A1 (CP2102N):
  /dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_ee5a3b581464ef1196f5daa9c169b110-if00-port0
  → in raspi/modules/lidar.py → Lidar.__init__ (bereits eingetragen)
```

Alle angeschlossenen Geräte auflisten:
```bash
ls /dev/serial/by-id/
```

---

## ESP32 – UART-Protokoll (115200 Baud, Newline-terminiert)

### Raspi → ESP32

| Befehl | Bedeutung |
|---|---|
| `DD{mm}` | Geradeaus fahren, mm positiv = vorwärts, negativ = rückwärts |
| `TA{deg}` | Relativ drehen, deg positiv = Uhrzeigersinn |
| `ST` | Sofort bremsen (MOVING → STOPPING → PAUSED, kein Ack) |
| `RS` | Weiterfahren nach ST (PAUSED → MOVING, verbleibende Distanz) |
| `SP{x};{y};{t}` | Odometrie setzen (kein Ack) |

### ESP32 → Raspi

| Antwort | Bedeutung |
|---|---|
| `OK` | Befehl vollständig ausgeführt |
| `INTERRUPTED` | Durch ST abgebrochen (während PAUSED) |
| `ERR` | Unbekannter Befehl |

### Zustandsautomat (ESP32 stepperTask)

```
IDLE ──DD/TA──► MOVING ──ST──► STOPPING ──stillstand──► PAUSED
                                                             │
                 ◄──────────────── RS ──────────────────────┘

PAUSED ──ST──► IDLE  (sendet INTERRUPTED)
MOVING ──fertig──► IDLE  (sendet OK)
```

> ST während MOVING bremst kontrolliert ab und speichert das Originalziel.
> RS berechnet die verbleibende Strecke und fährt weiter.
> Ein zweites ST während PAUSED bricht ab und sendet INTERRUPTED.

### FreeRTOS-Architektur (ESP32)

- **Core 0 – stepperTask**: AccelStepper-Tight-Loop ohne `vTaskDelay`, `disableCore0WDT()` notwendig
- **Core 1 – uartTask**: `Serial.available()` polling mit `vTaskDelay(1ms)`
- Kommunikation: FreeRTOS-Queue (`cmdQueue`, Tiefe 8), volatile flags (`stopFlag`, `resumeFlag`), Mutex (`serialMtx`)

---

## Raspi – Software-Architektur

```
raspi/
├── main.py              Hauptprogramm: Robot-Klasse, TCP-Server, Spielablauf
├── client.py            CLI-Client (per SSH; verbindet auf 127.0.0.1:5001)
├── start.sh             Interaktiver Start (Team-Auswahl, stoppt eurobot.service)
├── status.py            Hardware-Status-Check ohne Bewegungen
├── lidar_test.py        Live-Lidar-Visualisierung im Terminal
├── pullcord_test.py     GPIO-22-Test
├── ACTIONS.md           Vollständige Aktions-Referenz
├── eurobot.service      systemd-Unit
└── modules/
    ├── esp32.py         Seriell zum ESP32, dead-reckoning Odometrie
    ├── servos.py        STServo-Bus (8 Servos)
    ├── gripper.py       Greifer-Sequenzen (nutzt servos.py)
    ├── task.py          Aktions-Dispatcher (Taktik-Ausführung)
    ├── lidar.py         RPLIDAR, Scan-Thread, Hinderniserkennung
    ├── camera.py        PiCamera2, ArUco-Erkennung
    └── STservo_sdk/     Feetech/Waveshare STS-Protokoll-SDK
```

### Spielablauf (main.py)

```
Robot.__init__
  └── Hardware initialisieren (ESP32, Servos, Lidar, Camera)

handle_cmd("ready")
  └── _flow_ready()
       1. State = HOMING  →  _do_homing()  [hg + hm]
       2. State = READY   →  warte auf GPIO 22 HIGH
       3. State = RUNNING →  _run_tactic()
            ├── _game_timer() startet: asyncio.sleep(98s) → Stopp
            └── task.run() loop bis keine Aktionen mehr
       4. State = DONE
```

### Gegnererkennung + Pause-Resume

```
esp32.drive_distance(mm) / turn_angle(deg)
  └── _wait_for_ok(direction, lidar)
       ┌─ Schleife jede 10 ms ─────────────────────────┐
       │  lidar.get_stop()  →  Hindernis?              │
       │    ja, noch nicht gestoppt → sende "ST"       │
       │    nein, war gestoppt     → sende "RS"        │
       │  "OK" empfangen  → return True  (pos updaten) │
       │  "INTERRUPTED"   → return False (pos behalten)│
       └───────────────────────────────────────────────┘
```

Odometrie wird **nur** bei vollständig abgeschlossener Fahrt (`OK`) aktualisiert. Bei `INTERRUPTED` (echter Abbruch durch manuelles ST) bleibt die letzte bekannte Position erhalten.

### Odometrie (Dead-Reckoning)

```python
# Nach drive_distance(mm):
rad = math.radians(theta)
x += mm * math.sin(rad)
y += mm * math.cos(rad)

# Nach turn_angle(deg):
theta = (theta + deg) % 360
```

Koordinatensystem:
```
x: 0 (links) → 3000 mm (rechts)   [Zuschauerperspektive]
y: 0 (vorne) → 2000 mm (hinten)

θ = 0°:   fährt in +y (zur Hinterwand)
θ = 90°:  fährt in +x (nach rechts)
θ = 180°: fährt in -y (zum Zuschauer)
θ = 270°: fährt in -x (nach links)

Startposition nach Wall-Homing:
  Blau:  x=135,  y=1945, θ=180°
  Gelb:  x=2865, y=1945, θ=0°
```

### Team-Spiegelung

Alle Taktiken werden in Blau-Koordinaten definiert. `task.py` spiegelt automatisch für Gelb:

| Wert | Blau | Gelb |
|---|---|---|
| x-Koordinate | x | 3000 − x |
| y-Koordinate | y | y (unverändert) |
| Winkel (absolut) | θ | (180 − θ) mod 360° |
| dd-Vorzeichen | +vorwärts | −vorwärts |
| ta-Vorzeichen | +rechts | −rechts |

---

## Starten

### Manuell (Entwicklung / Test)

```bash
cd /home/eurobot/eurobot-2026/raspi

# Interaktives Startskript (empfohlen):
bash start.sh

# Oder direkt:
python3 main.py --team blue
python3 main.py --team yellow
```

### Client verbinden (zweites SSH-Fenster)

```bash
python3 /home/eurobot/eurobot-2026/raspi/client.py
```

Befehle im Client:
```
status              aktuellen Zustand anzeigen
team blue|yellow    Team setzen
tactic <n>          Taktik wählen (Nummern aus TACTICS-Dict in main.py)
ready               Homing → warten auf Zugschnur → Taktik starten
home                nur Homing (ohne Spielstart)
stop                Notfall-Stopp, zurück auf IDLE
drive <mm>          Test: fahre mm vorwärts
turn <deg>          Test: drehe deg Grad
servo <id> <pos>    Test: Servo direkt setzen
gripper open|close|home
help                alle Befehle
```

### Autostart via systemd

```bash
sudo cp raspi/eurobot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable eurobot
sudo systemctl start eurobot

# Status und Log:
sudo systemctl status eurobot
journalctl -u eurobot -f
cat raspi/eurobot.log
```

---

## Taktiken definieren

In `raspi/main.py` → `TACTICS`-Dict:

```python
TACTICS = {
    1: [['dd1000']],              # Phase 1: 1 m vorwärts
    2: [['dd500', 'ta90'],        # Phase 1: 500 mm, dann 90° drehen
        ['dd300', 'gr', 'ip5']],  # Phase 2: 300 mm, greifen, +5 Punkte
}
```

- Homing (`hg` + `hm`) wird von `ready` **automatisch davor** ausgeführt.
- Mehrere innere Listen = mehrere Phasen, die nacheinander ausgeführt werden.
- Nach 98 Sekunden stoppt `_game_timer()` alles automatisch.

Vollständige Aktions-Referenz: [`raspi/ACTIONS.md`](raspi/ACTIONS.md)

---

## ESP32 flashen

```bash
cd ESP

# Nur kompilieren:
pio run

# Kompilieren + flashen:
pio run -t upload
# Hinweis: Falls "No serial data received" → BOOT-Taste am ESP32 gedrückt halten
# während pio den Upload startet, dann loslassen

# Seriellen Monitor:
pio device monitor -b 115200
```

---

## Test-Skripte

```bash
cd raspi

# Lidar live anzeigen (Hinderniserkennung im Terminal):
python3 lidar_test.py

# Zugschnur testen (GPIO 22):
python3 pullcord_test.py

# Hardware-Status (ESP32, Servos, Lidar, Kamera, GPIO):
python3 status.py
```

---

## Dateistruktur

```
eurobot-2026/
├── ESP/                        PlatformIO-Projekt (ESP32)
│   ├── platformio.ini          Board: esp32dev, lib: AccelStepper
│   └── src/main.cpp            Stepper-Controller (FreeRTOS, 2 Kerne)
├── raspi/
│   ├── main.py                 Hauptprogramm (TCP-Server, Spiellogik)
│   ├── client.py               CLI-Client
│   ├── start.sh                Interaktiver Start
│   ├── status.py               Hardware-Check
│   ├── lidar_test.py           Lidar-Test
│   ├── pullcord_test.py        Zugschnur-Test
│   ├── eurobot.service         systemd-Unit
│   ├── ACTIONS.md              Aktions-Referenz
│   └── modules/
│       ├── esp32.py            ESP32-Kommunikation + Odometrie
│       ├── servos.py           STServo-Bus (kalibrierte Positionen)
│       ├── gripper.py          Greifer-Sequenzen
│       ├── task.py             Aktions-Dispatcher
│       ├── lidar.py            RPLIDAR + Hinderniserkennung
│       ├── camera.py           PiCamera2 + ArUco
│       └── STservo_sdk/        Feetech STS-Protokoll-SDK
├── PINOUT.md                   Hardware-Pinout (detailliert)
├── ACTIONS.md → raspi/ACTIONS.md
└── images/bot.png
```

---

## Offene Punkte (TODO)

- [ ] ESP32 USB-Pfad in `raspi/modules/esp32.py` → `PORT` eintragen (aktuell `TODO_SET_ESP32_PORT`)
- [ ] Lift-Positionen kalibrieren: Servo ID 3 (Lift A) und ID 6 (Lift B) – alle 4 Positionen in `servos.py`
- [ ] Taktiken in `raspi/main.py` → `TACTICS` mit echten Spielzügen befüllen
- [ ] PINOUT.md aktualisieren (veraltete Servo-Positionen und GPIO-17-Eintrag entfernen)
