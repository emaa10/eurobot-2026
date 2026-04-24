# Eurobot 2026 – Pinout

## Raspberry Pi (BCM-Nummerierung)

| GPIO | Pin | Funktion | Pegel |
|---|---|---|---|
| **22** | 15 | Zugschnur | Pull-Up: LOW = Schnur drin, HIGH-Flanke = Spielstart |

> Team-Auswahl erfolgt beim Start über `start.sh` (interaktiv) oder `--team blue|yellow`.

### USB-Geräte am Raspberry Pi

| Gerät | Chip | Device-Pfad |
|---|---|---|
| ESP32 | CP2102 | `/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_...-if00` |
| STServo-Adapter (Seriennr. 5A46083059) | CH340 | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A46083059-if00` |
| RPLIDAR A1 | CP2102N | `/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_ee5a3b581464ef1196f5daa9c169b110-if00-port0` |

Nach erstem Anschließen Pfade prüfen: `ls /dev/serial/by-id/`
Dann ESP32-Pfad in `raspi/modules/esp32.py → PORT` eintragen.

---

## ESP32 DevKit v1 – Stepper-Pins

| GPIO | Funktion | Anmerkung |
|---|---|---|
| **26** | STEP – Rechter Motor | |
| **27** | DIR – Rechter Motor | |
| **25** | DIR – Linker Motor | Gespiegelt montiert → `setPinsInverted(true)` im Code |
| **33** | STEP – Linker Motor | |

UART0 (GPIO 1 TX / GPIO 3 RX) über USB (CP2102) → Raspi. Kein separates Kabel nötig.

### Gesperrte Pins

| GPIO | Grund |
|---|---|
| 6–11 | Intern: Flash |
| 0, 2, 12, 15 | Boot-Mode-Pins |
| 1, 3 | UART0 (für Raspi-Kommunikation belegt) |

---

## TB6600 Stepper-Treiber

```
ESP32 GPIO26 ──► PUL+  ]
ESP32 GPIO27 ──► DIR+  ]  TB6600 – Rechter Motor
GND          ──► PUL-  ]
GND          ──► DIR-  ]

ESP32 GPIO33 ──► PUL+  ]
ESP32 GPIO25 ──► DIR+  ]  TB6600 – Linker Motor (gespiegelt montiert!)
GND          ──► PUL-  ]
GND          ──► DIR-  ]

Motorspannung 9–42 V an VCC/GND der Treiber
```

DIP-Schalter am TB6600 auf **1/16 Microstep** → passt zu `STEPS_PER_REV = 3200` im ESP-Code.

Motor-Geometrie im ESP:
- `STEPS_PER_REV = 3200` (200 Vollschritte × 16 Microsteps)
- `WHEEL_DIAM_MM = 60`
- `WHEELBASE_MM  = 200`
- `MAX_SPEED = 1500 steps/s`
- `ACCELERATION = 1200 steps/s²`

---

## STServo Bus (Halbduplex UART, 1 MBaud)

Alle 8 Servos auf einem Bus. Gesteuert über USB-Adapter am Raspi.

### Frontgreifer (von links nach rechts)

| ID | Montageposition | Position auf/hoch | Position zu/runter |
|---|---|---|---|
| **2** | Ganz links (außen) | 1048 | 2000 |
| **1** | Zweiter von links (innen) | 1500 | 2500 |
| **11** | Zweiter von rechts (innen) | 1048 | 2100 |
| **9** | Ganz rechts (außen) | 1048 | 2048 |

### Lift-Modul

| ID | Funktion | Position hoch | Position runter |
|---|---|---|---|
| **3** | Lift A | TODO | TODO |
| **6** | Lift B | TODO | TODO |

### Winker (relative Positionierung, kein Absolutwert)

| ID | Funktion | Bewegung runter | Bewegung hoch |
|---|---|---|---|
| **7** | Winker links | −1707 steps (150°) | +1707 steps (150°) |
| **8** | Winker rechts | −1707 steps (150°) | +1707 steps (150°) |

`WINKER_STEPS = 1707` entspricht 150° (1707/4096 × 360° ≈ 150°).

---

## Serielles Protokoll ESP32 ↔ Raspi (115200 Baud, `\n`-terminiert)

### Raspi → ESP32

| Befehl | Bedeutung |
|---|---|
| `DD{mm}` | Geradeaus fahren (+ vorwärts, − rückwärts) |
| `TA{deg}` | Relativ drehen (+ Uhrzeigersinn, − gegen) |
| `ST` | Bremsen → PAUSED (kein Ack, Ziel gespeichert) |
| `RS` | Weiterfahren aus PAUSED (verbleibende Distanz) |
| `SP{x};{y};{t}` | Odometrie setzen (kein Ack) |

### ESP32 → Raspi

| Antwort | Bedeutung |
|---|---|
| `OK` | Fahrbefehl vollständig abgeschlossen |
| `INTERRUPTED` | Echter Abbruch (ST während PAUSED) |
| `ERR` | Unbekannter Befehl |

---

## Spielfeld-Koordinaten

```
x: 0 (links) → 3000 mm (rechts)   [Zuschauerperspektive]
y: 0 (vorne) → 2000 mm (hinten)

θ = 0°:   Richtung Hinterwand (+y)
θ = 90°:  Richtung rechts (+x)
θ = 180°: Richtung Zuschauer (−y)
θ = 270°: Richtung links (−x)

Startzone Blau:  x = 0–450,     y = 1550–2000
Startzone Gelb:  x = 2550–3000, y = 1550–2000

Nach Wall-Homing (Drehachse 55 mm von Hinterwand, 135 mm von Seitenwand):
  Blau:  x = 135,  y = 1945, θ = 180°
  Gelb:  x = 2865, y = 1945, θ = 0°
```
