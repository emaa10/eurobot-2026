# Eurobot 2026 – Vollständiges Pinout

## Raspberry Pi  (BCM-Nummerierung)

| GPIO (BCM) | Pin | Funktion | Beschreibung |
|---|---|---|---|
| GPIO 17 | 11 | Input, Pull-Up | **Team Select**: LOW = Blau, HIGH = Gelb |
| GPIO 22 | 15 | Input, Pull-Up | **Zugschnur**: LOW = Schnur drin, HIGH-Flanke = Start |

### USB-Geräte am Raspberry Pi
| Gerät | Typ | Device-Pfad |
|---|---|---|
| ESP32 (CP2102) | USB-UART | `/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_...-if00` |
| STServo Controller (CH340) | USB-UART | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083062-if00` |
| Lidar | USB-Serial | `/dev/serial/by-id/usb-Silicon_Labs_...-if00` |

> Nach dem ersten Anschließen Pfade prüfen: `ls /dev/serial/by-id/`
> Dann in `raspi/modules/esp32.py` → `PORT` und `raspi/modules/servos.py` → `PORT` eintragen.

---

## ESP32 DevKit v1 (38-Pin)  –  nur Stepper-Antrieb

| ESP32 GPIO | Funktion | Anmerkung |
|---|---|---|
| **GPIO 25** | STEP – Linker Motor | |
| **GPIO 26** | DIR  – Linker Motor | HIGH = vorwärts |
| **GPIO 32** | STEP – Rechter Motor | |
| **GPIO 33** | DIR  – Rechter Motor | LOW = vorwärts (gespiegelt montiert) |

### Serielle Kommunikation ESP32 ↔ Raspberry Pi
UART0 (GPIO 1 TX / GPIO 3 RX) über USB (CP2102). Kein separates Kabel nötig.

### Gesperrte Pins
| GPIO | Grund |
|---|---|
| GPIO 6–11 | Intern: Flash |
| GPIO 0, 2, 12, 15 | Boot-Mode |
| GPIO 1, 3 | UART0 (belegt) |

---

## Stepper-Treiber Verdrahtung (TB6600)

```
ESP32 GPIO25 ──► PUL+  ┐
ESP32 GPIO26 ──► DIR+  │  TB6600 Linker Motor
GND          ──► PUL-  │  (PUL-/DIR- auf GND)
GND          ──► DIR-  │
Vmotor       ──► VCC   ┘  Motorspannung 9–42 V
Motor A+/A-/B+/B- ──► Spulen

ESP32 GPIO32 ──► PUL+  ┐
ESP32 GPIO33 ──► DIR+  │  TB6600 Rechter Motor (gespiegelt montiert!)
GND          ──► PUL-  │
GND          ──► DIR-  ┘
```

> TB6600 Microstepping per DIP-Schalter einstellen.
> Bei STEPS_PER_REV=200 im ESP32-Code → SW auf 1/1 (Vollschritt).
> Für ruhigeren Lauf: 1/8 Microstepping → STEPS_PER_REV auf 1600 setzen.

---

## STServo Bus – 8 Servos (USB-Adapter am Raspi)

Halbduplex UART, 1 MBaud. Alle Servos auf einem Bus.

### Frontgreifer (von links nach rechts)
| Servo-ID | Funktion | Positionen (raw) |
|---|---|---|
| **2** | Greifer links außen | 100 = auf, 630 = zu |
| **1** | Greifer links innen | 4000 = auf, 3450 = zu, 3000 = home |
| **11** | Greifer rechts innen | 3825 = auf, 2500 = zu  ← **TODO kalibrieren** |
| **9** | Greifer rechts außen | 1800 = auf, 2800 = zu  ← **TODO kalibrieren** |

### Greifer Heben/Senken
| Servo-ID | Funktion | Positionen (raw) |
|---|---|---|
| **?** | Greifer hoch/runter links | TODO |
| **?** | Greifer hoch/runter rechts | TODO |

### Thermometer
| Servo-ID | Funktion | Positionen (raw) |
|---|---|---|
| **?** | Thermometer 1 | TODO |
| **?** | Thermometer 2 | TODO |

---

## Serielles Protokoll ESP32 ↔ Raspi  (115200 Baud, Newline-terminiert)

| Richtung | Befehl | Bedeutung |
|---|---|---|
| Raspi→ESP32 | `DD{mm}` | Fahre mm vorwärts (negativ = rückwärts) |
| Raspi→ESP32 | `TA{deg}` | Drehe deg Grad (positiv = Uhrzeigersinn) |
| Raspi→ESP32 | `ST` | Sofort stoppen |
| Raspi→ESP32 | `SP{x};{y};{t}` | Odometrie setzen |
| ESP32→Raspi | `OK` | Befehl fertig |
| ESP32→Raspi | `INTERRUPTED` | Durch ST abgebrochen |
| ESP32→Raspi | `ERR` | Unbekannter Befehl |

---

## Spielfeld-Koordinaten (Eurobot 2026)

```
x: 0 (links) → 3000 mm (rechts)    [Zuschauerperspektive]
y: 0 (vorne) → 2000 mm (hinten)

Startzone Blau:  x=0–450,     y=1550–2000  (hintere linke Ecke)
Startzone Gelb:  x=2550–3000, y=1550–2000  (hintere rechte Ecke)

Winkelkonvention:
  θ=0:   fährt in +y (Richtung Hinterwand)
  θ=90:  fährt in +x (nach rechts)
  θ=180: fährt in -y (zum Zuschauer)
  θ=270: fährt in -x (nach links)

Nach Wall-Homing:
  Drehachse 55 mm von Hinterwand → y_rot = 1945 mm
  Drehachse 135 mm von linker Wand
  Blau:  x=135,  y=1945, θ=180
  Gelb:  x=2865, y=1945, θ=0
```

---

## Startablauf

```
python3 raspi/main.py [taktik] [startpos]

  1. Team-Farbe von GPIO 17 lesen
  2. Homing (Wand-Kalibrierung + Greifer-Home)
  3. Warten auf Zugschnur (GPIO 22)
  4. Taktik ausführen (99 s)
```
