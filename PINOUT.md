# Eurobot 2026 – Vollständiges Pinout

## Raspberry Pi  (BCM-Nummerierung)

| GPIO (BCM) | Pin | Funktion | Beschreibung |
|---|---|---|---|
| GPIO 14 | 8  | TXD0 (USB-Serial) | TX → ESP32 via USB |
| GPIO 15 | 10 | RXD0 (USB-Serial) | RX ← ESP32 via USB |
| GPIO 17 | 11 | Input, Pull-Up | **Team Select**: LOW = Blau, HIGH = Gelb |
| GPIO 22 | 15 | Input, Pull-Up | **Zugschnur (Pull Cord)**: LOW = kein Start, HIGH-Flanke = Start |
| GPIO 2  | 3  | SDA (I²C) | (reserviert, falls I²C-Gerät) |
| GPIO 3  | 5  | SCL (I²C) | (reserviert, falls I²C-Gerät) |

### USB-Geräte am Raspberry Pi
| Gerät | Typ | Device-Pfad (Beispiel) |
|---|---|---|
| ESP32 (CP2102) | USB-UART | `/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB...` |
| STServo Controller | USB-UART (CH340) | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083062-if00` |
| Lidar (RPLIDAR/YDLidar) | USB-Serial | `/dev/serial/by-id/usb-Silicon_Labs_...` |

> **Hinweis:** Nach dem ersten Anschließen des ESP32 den tatsächlichen Pfad prüfen:
> ```bash
> ls /dev/serial/by-id/
> ```
> Dann in `raspi/modules/esp32.py` → `PORT = '...'` eintragen.

---

## ESP32 DevKit v1 (38-Pin)

### Antrieb (2× Stepper-Treiber, z.B. A4988 / DRV8825 / TMC2208)

| ESP32 GPIO | Funktion | Anmerkung |
|---|---|---|
| **GPIO 25** | STEP – Linker Motor | |
| **GPIO 26** | DIR  – Linker Motor | HIGH = vorwärts |
| **GPIO 32** | STEP – Rechter Motor | |
| **GPIO 33** | DIR  – Rechter Motor | LOW = vorwärts (Motor physisch gespiegelt!) |
| **GPIO 27** | ENABLE (shared, aktiv LOW) | LOW = aktiv; beide Antriebsstepper |

### Lift-Stepper Greifer (3× Stepper-Treiber)

| ESP32 GPIO | Funktion | Anmerkung |
|---|---|---|
| **GPIO 18** | STEP – Lift Rechts | |
| **GPIO 19** | DIR  – Lift Rechts | HIGH = aufwärts |
| **GPIO 21** | STEP – Lift Mitte | |
| **GPIO 22** | DIR  – Lift Mitte | HIGH = aufwärts |
| **GPIO 23** | STEP – Lift Links | |
| **GPIO  5** | DIR  – Lift Links | HIGH = aufwärts |
| **GPIO  4** | ENABLE Lift (shared, aktiv LOW) | alle 3 Lift-Stepper |

### Endstops Lift (aktiv LOW)

| ESP32 GPIO | Funktion | Wichtig! |
|---|---|---|
| **GPIO 34** | Endstop Lift Rechts | **Input-Only**, **kein interner Pull-up** → extern 10 kΩ nach 3.3 V |
| **GPIO 35** | Endstop Lift Mitte  | **Input-Only**, **kein interner Pull-up** → extern 10 kΩ nach 3.3 V |
| **GPIO 36** | Endstop Lift Links  | **Input-Only**, **kein interner Pull-up** → extern 10 kΩ nach 3.3 V |

### Serielle Kommunikation ESP32 ↔ Raspberry Pi

| ESP32 | Funktion |
|---|---|
| **UART0** (GPIO 1/TX, GPIO 3/RX) | USB → Raspberry Pi (via eingebautem CP2102/CH340) |

> GPIO 1 und 3 werden automatisch durch den USB-UART-Chip verwendet.
> Kein zusätzliches Kabel nötig – nur USB-Kabel ESP32 ↔ Raspi.

### Nicht verwenden!
| GPIO | Grund |
|---|---|
| GPIO 6–11 | Intern: Flash-Speicher |
| GPIO 0, 2, 12, 15 | Boot-Mode-Pins (vorsichtig verwenden) |
| GPIO 1, 3 | UART0 (bereits belegt für Raspi) |

---

## Stepper-Treiber Verdrahtung (A4988 / DRV8825)

```
ESP32 GPIO25 ──► STEP  ┐
ESP32 GPIO26 ──► DIR   │  Treiber Linker Motor
ESP32 GPIO27 ──► EN    │  (aktiv LOW)
GND          ──► GND   │
3.3V / 5V    ──► VDD   │  Logikspannung
Vmotor       ──► VMOT  ┘  Motorspannung (12–24V)
Motor A1/A2/B1/B2 ──► Spulen

Microstepping (16×):
A4988:  MS1=HIGH, MS2=HIGH, MS3=HIGH
DRV8825: M0=HIGH, M1=HIGH,  M2=HIGH
```

## Endstop-Schaltung (für GPIO 34-36)

```
3.3V ──┬── 10kΩ ──► GPIO 34/35/36
       │
       └── Endstop-Schalter (NO) ──► GND
```
Wenn Schalter schließt: GPIO liest LOW = Endstop ausgelöst.

---

## STServo Bus (Greifer-Servos, über separaten USB-Controller)

| Servo-ID | Funktion |
|---|---|
| 1  | Rechter Grip |
| 2  | Linker Grip |
| 3  | Mitte Lift |
| 5  | (reserviert) |
| 6  | Flagge |
| 7  | Mitte Grip |
| 8  | Platten-Grip |
| 9  | Platten-Rotation |
| 10 | Linke Rotation |
| 11 | Rechte Rotation |

Alle Servos laufen auf einem Halbduplex-Bus (UART). Der USB-Serial-Adapter
fungiert als Bus-Master (1 MBaud).

---

## Spielfeld-Koordinaten (Eurobot 2026)

```
x: 0 (links, Zuschauersicht) → 3000 mm (rechts)
y: 0 (vorne, Zuschauer)      → 2000 mm (hinten, Körnerkammer)

Startzone Blau:  x=0–450,    y=1550–2000  (hintere linke Ecke)
Startzone Gelb:  x=2550–3000, y=1550–2000  (hintere rechte Ecke)

Roboter-Nullwinkel  θ=0:   fährt in +y Richtung (nach hinten)
                    θ=90:  fährt in +x Richtung (nach rechts)
                    θ=180: fährt in -y Richtung (zum Zuschauer)
                    θ=270: fährt in -x Richtung (nach links)

Drehachse am Roboter:
  55 mm von der Hinterkante  → y_rot = 2000 - 55 = 1945 mm nach Wall-Homing
  135 mm von der linken Kante (Zuschauersicht)
  Blau nach Homing: x=135,  y=1945, θ=180
  Gelb nach Homing: x=2865, y=1945, θ=0  (ESP32-intern, gespiegelt)
```
