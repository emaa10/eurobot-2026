# Eurobot 2026 – Task-Aktionen

Taktiken werden in `raspi/main.py` als Listen von Aktions-Strings definiert:

```python
TACTICS = {
    1: [['hg', 'hm', 'dd1000', 'gr', 'ip3']],
    2: [['hg', 'hm', 'dp750;500', 'gr', 'ip3']],
}
```

Jede innere Liste ist eine Phase. Mehrere Phasen werden nacheinander ausgeführt.
Der Dispatcher läuft in `raspi/modules/task.py → perform_action()`.

---

## Fahren  (→ ESP32 via seriellem Protokoll)

### `dd{mm}` – Drive Distance
Fahre geradeaus. Positiv = vorwärts, negativ = rückwärts.
Für Gelb wird das Vorzeichen automatisch gespiegelt.

```
dd500     → 500 mm vorwärts
dd-200    → 200 mm rückwärts
```

### `ta{deg}` – Turn Angle (relativ)
Drehe um einen relativen Winkel. Positiv = Uhrzeigersinn.
Für Gelb wird das Vorzeichen gespiegelt.

```
ta90      → 90° im Uhrzeigersinn
ta-45     → 45° gegen den Uhrzeigersinn
```

### `tt{deg}` – Turn To (absolut)
Drehe auf einen absoluten Winkel (0–359°) in Blau-Koordinaten.
Für Gelb wird der Winkel automatisch gespiegelt (180° − θ).

```
tt180     → schaut zur Zuschauerwand (Blau-Standard-Startwinkel)
tt0       → schaut zur Hinterwand
tt90      → schaut nach rechts
```

### `dp{x};{y}` oder `dp{x};{y};{theta}` – Drive to Point
Dreht zuerst in Richtung des Zielpunkts, fährt dann geradeaus hin.
Koordinaten in Blau-Koordinaten (mm); für Gelb wird x automatisch gespiegelt (3000 − x).
Optionaler dritter Wert: nach Ankunft noch auf `theta` ausrichten.

```
dp750;500        → fahre zu x=750, y=500
dp750;500;90     → fahre zu x=750, y=500, dann auf 90° drehen
```

### `sp{x};{y};{theta}` – Set Position
Setzt die interne Odometrie des Raspberry Pi manuell.
Nützlich nach manuellem Aufstellen ohne Homing.
Koordinaten in Blau-Koordinaten; für Gelb automatisch gespiegelt.

```
sp135;1945;180   → Blau-Startposition nach Wall-Homing
```

### `gp` – Get Position
Gibt die aktuelle Odometrie-Position auf stdout aus (Debug).

```
gp   → pos: 135, 1945, 180.0
```

### `es` – Emergency Stop
Sendet sofort `ST` an den ESP32. Bricht den aktuellen Fahrbefehl ab.

---

## Homing

### `hm` – Autonomous Wall Homing
Vollautomatische Positionskalibrierung gegen die Wände.
Setzt danach die Odometrie auf die bekannte Drehachsen-Position.

**Ablauf:**
1. Rückwärts 300 mm in die Hinterwand (y = 2000 mm)
2. 50 mm von der Hinterwand wegfahren
3. +90° drehen (Blau → Richtung linke Wand x = 0; Gelb → rechte Wand x = 3000)
4. 300 mm in die Seitenwand fahren
5. 50 mm von der Seitenwand wegfahren
6. −90° zurückdrehen

**Ergebnis:**
- Blau:  x = 135 mm,  y = 1945 mm,  θ = 180°
- Gelb:  x = 2865 mm, y = 1945 mm,  θ = 0°

Drehachse des Roboters liegt 55 mm von der Hinterkante und 135 mm von der linken Kante.

### `hg` – Home Gripper
Fährt alle Servos in die definierte Home-Position (alle Greifer auf, Arm in Ruheposition).
Sollte immer **vor** `hm` ausgeführt werden, damit der Arm nicht die Wand berührt.

```
hg   → Greifer öffnen, Arm home
```

---

## Greifer  (→ STServos direkt am Raspi)

Der Greifer hat 4 Frontgreifer (von links nach rechts: ID 2, 1, 11, 9),
2 Servos zum Heben/Senken, und 2 Thermometer-Servos.

### `gr` – Greifen (alle zu)
Schließt alle 4 Frontgreifer gleichzeitig.

### `go` – Öffnen (alle auf)
Öffnet alle 4 Frontgreifer gleichzeitig.

### `gi` – Innen greifen
Schließt nur die beiden inneren Greifer (ID 1 und ID 11).

### `ga` – Außen greifen
Schließt nur die beiden äußeren Greifer (ID 2 und ID 9).

### `ws{id};{pos}` – Write Servo (manuell)
Setzt einen einzelnen Servo auf eine raw-Position. Nur für Kalibrierung / Debugging.

```
ws11;3000    → Servo ID 11 auf Position 3000
ws2;100      → Servo ID 2 auf Position 100 (auf)
```

---

## Punkte

### `ip{n}` – Increase Points (fix)
Addiert n Punkte zum internen Punktezähler.
Wird am Ende jeder Aktions-Phase an den Client gemeldet (falls verbunden).

```
ip3    → +3 Punkte
ip10   → +10 Punkte
```

### `ic` – Increase Points via Camera
Wartet 1 Sekunde, lässt dann die Kamera Stapel zählen (ArUco-Erkennung),
und addiert Punkte entsprechend der Regelwerk-Tabelle:

| Stapel-Anzahl | Punkte |
|---|---|
| 1 | 4 |
| 2 | 12 |
| 3 | 28 |

---

## Koordinatensystem & Spiegelung

Alle Koordinaten und Winkel werden in **Blau-Koordinaten** angegeben.
Für das gelbe Team spiegelt der Task-Dispatcher automatisch:

| Wert | Blau | Gelb |
|---|---|---|
| x | x | 3000 − x |
| y | y | y (unverändert) |
| theta (absolut) | θ | (180 − θ) mod 360 |
| dd-Vorzeichen | +vorwärts | −vorwärts (gespiegelt) |
| ta-Vorzeichen | +rechts | −rechts (gespiegelt) |

---

## Taktik-Beispiel

```python
# Taktik 1: Homing, 1 m vorwärts, greifen, Punkte zählen
TACTICS = {
    1: [['hg', 'hm', 'dd1000', 'gr', 'ic']],
}
```

Ausführungsreihenfolge:
1. `hg` → Greifer in Home-Position
2. `hm` → Wand-Homing, Odometrie gesetzt
3. `dd1000` → 1000 mm vorwärts
4. `gr` → Alle Greifer schließen
5. `ic` → Kamera zählt Stapel, Punkte werden addiert

---

## Starten

```bash
# Interaktives Menü:
python3 raspi/main.py

# Direkt mit Taktik 2, Startposition 1:
python3 raspi/main.py 2 1
```

Ablauf nach dem Start:
1. Team-Farbe von GPIO 17 lesen
2. Taktik initialisieren
3. Homing ausführen (sofern in Taktik enthalten)
4. Auf Zugschnur warten (GPIO 22, HIGH-Flanke)
5. 99-Sekunden-Timer starten
6. Taktik ausführen
7. Stopp
