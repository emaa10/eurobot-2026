# SIMA2 – Pullcord + 1 m Fahrt mit Gegnererkennung

## Architektur

Dual-Core auf RP2040 (Pico2):

| Core | Datei | Aufgabe |
|------|-------|---------|
| 0 | `main.cpp` / `robot.cpp` | ToF-Sensorloop 50 Hz, `opponent_detected` setzen |
| 1 | `main.cpp` | Zugschnur warten → `driveMM(1000)` |

## Ablauf

1. Core0 startet, initialisiert beide VL53L0X (I2C0 + I2C1), pollt @50 Hz mit Median-3-Filter
2. Core1 wartet 2 s (bis Core0 fertig init), dann wartet auf Zugschnur (GPIO 21 LOW)
3. Zugschnur gezogen → `driveMM(1000)` fährt 1 m vorwärts mit Rampe
4. Gegnererkennung: sobald beide ToF < 500 mm für 5 Frames → Motoren aus, warten
5. Bahn frei (beide > 540 mm) → Motoren wieder an, weiterfahren
6. Nach 1 m: Motoren aus, Endlos-Halt

## Pinbelegung

| Signal | GPIO |
|--------|------|
| L_STEP | 0 |
| L_DIR | 1 |
| L_EN | 7 |
| R_STEP | 10 |
| R_DIR | 9 |
| R_EN | 15 |
| I2C1 SDA/SCL (ToF links) | 2/3 |
| I2C0 SDA/SCL (ToF rechts) | 12/13 |
| Zugschnur | 21 |

## Kalibrierung

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| STEPS_PER_MM | 0.98 | ~980 Steps/m |
| DELAY_START_US | 6000 | Anlauf-Verzögerung |
| DELAY_MIN_US | 2500 | Vollspeed |
| STOP_MM | 500 | Stoppschwelle |
| RESUME_MM | 540 | Weiterfahrschwelle |
| BELOW_LIMIT | 5 | Frames für Entprellung |
