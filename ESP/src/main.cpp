/*
 * Eurobot 2026 – ESP32 Motor Controller
 *
 * Protokoll (Raspi → ESP32, newline-terminated):
 *   DD{mm}         Geradeaus fahren (+ vorwärts, – rückwärts)
 *   TA{deg}        Drehen um relativen Winkel (+ im Uhrzeigersinn)
 *   SL{r};{m};{l}  Lift-Stepper auf Absolutposition in mm setzen
 *   SH             Alle Lift-Stepper homen (fährt bis Endstop)
 *   ST             Antrieb pausieren (für Hindernis-Erkennung)
 *   RS             Antrieb fortsetzen nach ST
 *   SP{x};{y};{t}  Odometrie-Position setzen (nur Raspi-intern, ESP echot)
 *
 * ESP32 → Raspi:
 *   OK             Fahrbefehl (DD/TA) abgeschlossen
 *   ERR            Ungültiger Befehl
 *
 * Hinweis: SL, SH, ST, RS, SP senden KEIN OK (Raspi wartet nicht darauf).
 */

#include <Arduino.h>

// ═══════════════════════════════════════════════════════════════
//  PINOUT  (!!  AN ECHTE HARDWARE ANPASSEN  !!)
// ═══════════════════════════════════════════════════════════════

// Antrieb – Stepper-Treiber (A4988 / DRV8825 / TMC2208)
#define PIN_DRV_EN      27    // Enable, aktiv LOW (shared)
#define PIN_L_STEP      25    // Linker Motor STEP
#define PIN_L_DIR       26    // Linker Motor DIR
#define PIN_R_STEP      32    // Rechter Motor STEP
#define PIN_R_DIR       33    // Rechter Motor DIR  (Motor physisch gespiegelt montiert)

// Lift-Stepper (Greifer, 3×) – gleicher Treibertyp
#define PIN_LIFT_EN      4    // Enable, aktiv LOW (shared)
#define PIN_LFT_R_STEP  18
#define PIN_LFT_R_DIR   19
#define PIN_LFT_M_STEP  21
#define PIN_LFT_M_DIR   22
#define PIN_LFT_L_STEP  23
#define PIN_LFT_L_DIR    5

// Endstops Lift – aktiv LOW, extern 10 kΩ nach 3.3 V (GPIO 34-36 kein internen Pull-up!)
#define PIN_HOME_R      34
#define PIN_HOME_M      35
#define PIN_HOME_L      36

// ═══════════════════════════════════════════════════════════════
//  MECHANIK  (!!  AN ECHTE HARDWARE ANPASSEN  !!)
// ═══════════════════════════════════════════════════════════════

// Antrieb
#define STEPS_PER_REV        3200      // Schritte/Umdrehung inkl. Microstepping (z.B. 200 × 16)
#define WHEEL_DIAM_MM        65.0f     // Raddurchmesser in mm
#define WHEELBASE_MM        220.0f     // Radabstand (Kontaktpunkte) in mm
#define DRIVE_SPEED_MM_S    150.0f     // Fahrgeschwindigkeit mm/s
#define TURN_SPEED_MM_S     100.0f     // Drehgeschwindigkeit (Rad-Tangential) mm/s

// Lift
#define LIFT_STEPS_PER_MM    40.0f     // Schritte/mm Gewindestange (z.B. M5 × 1 mm Steigung × 40 MS)
#define LIFT_SPEED_MM_S      25.0f     // Normalbetrieb mm/s
#define LIFT_HOME_SPEED_MM_S  8.0f     // Homing-Geschwindigkeit mm/s

// ═══════════════════════════════════════════════════════════════
//  ABGELEITETE KONSTANTEN
// ═══════════════════════════════════════════════════════════════
static const float STEPS_PER_MM  = STEPS_PER_REV / (PI * WHEEL_DIAM_MM);
// Schritte pro Grad beim In-Place-Drehen (jedes Rad dreht einen Bogen = Radabstand × π × deg / 360)
static const float STEPS_PER_DEG = WHEELBASE_MM * PI / 360.0f * STEPS_PER_MM;

static uint32_t mmPerSToIntervalUs(float mmS, float stepsPerMm) {
    if (mmS <= 0.0f) return 5000;
    return (uint32_t)(1000000.0f / (mmS * stepsPerMm));
}

// ═══════════════════════════════════════════════════════════════
//  STEPPER-HILFSSTRUKTUR
// ═══════════════════════════════════════════════════════════════
struct Stepper {
    uint8_t  stepPin, dirPin;
    volatile long    pos    = 0;       // aktuelle Position in Schritten
    volatile long    target = 0;       // Zielposition in Schritten
    uint32_t intervalUs     = 1000;    // Schrittperiode
    uint32_t nextUs         = 0;

    void setSpeed(float mmS, float stepsPerMm) {
        intervalUs = mmPerSToIntervalUs(mmS, stepsPerMm);
    }

    // Einen Schritt ausführen wenn fällig. Rückgabe true = Schritt gemacht.
    bool runOnce() {
        if (pos == target) return false;
        uint32_t now = micros();
        if ((int32_t)(now - nextUs) < 0) return false;
        bool fwd = target > pos;
        digitalWrite(dirPin, fwd ? HIGH : LOW);
        delayMicroseconds(2);
        digitalWrite(stepPin, HIGH);
        delayMicroseconds(5);
        digitalWrite(stepPin, LOW);
        pos += fwd ? 1 : -1;
        nextUs = now + intervalUs;
        return true;
    }

    bool atTarget() const { return pos == target; }
    void setPos(long p)   { pos = target = p; }
};

// ═══════════════════════════════════════════════════════════════
//  GLOBALER ZUSTAND
// ═══════════════════════════════════════════════════════════════
Stepper drvL = { PIN_L_STEP,      PIN_L_DIR };
Stepper drvR = { PIN_R_STEP,      PIN_R_DIR };
Stepper lftR = { PIN_LFT_R_STEP,  PIN_LFT_R_DIR };
Stepper lftM = { PIN_LFT_M_STEP,  PIN_LFT_M_DIR };
Stepper lftL = { PIN_LFT_L_STEP,  PIN_LFT_L_DIR };

// Antriebszustand
enum DriveState : uint8_t { DS_IDLE, DS_RUNNING, DS_PAUSED };
volatile DriveState driveState = DS_IDLE;
volatile bool       sendOK     = false;

// ST/RS als Direktflags (zeitkritisch, bypassen Queue)
volatile bool stFlag = false;
volatile bool rsFlag = false;

// Lift-Homing
volatile bool liftHoming  = false;
volatile bool homeRdone   = false, homeMdone = false, homeLdone = false;

// Befehlsqueue (UART → Motor-Task)
enum CmdType : uint8_t { C_DD, C_TA, C_SL, C_SH };
struct Cmd { CmdType type; float a, b, c; };
QueueHandle_t cmdQ;

// ═══════════════════════════════════════════════════════════════
//  MOTOR-TASK  (Core 0 – zeitkritisch)
// ═══════════════════════════════════════════════════════════════

static void runLifts() {
    if (!liftHoming) {
        lftR.runOnce(); lftM.runOnce(); lftL.runOnce();
        return;
    }
    // Homing: nach unten fahren bis Endstop (aktiv LOW)
    if (!homeRdone) {
        if (digitalRead(PIN_HOME_R) == LOW) { lftR.setPos(0); homeRdone = true; }
        else                                  lftR.runOnce();
    }
    if (!homeMdone) {
        if (digitalRead(PIN_HOME_M) == LOW) { lftM.setPos(0); homeMdone = true; }
        else                                  lftM.runOnce();
    }
    if (!homeLdone) {
        if (digitalRead(PIN_HOME_L) == LOW) { lftL.setPos(0); homeLdone = true; }
        else                                  lftL.runOnce();
    }
    if (homeRdone && homeMdone && homeLdone) liftHoming = false;
}

void motorTask(void *) {
    // Output-Pins initialisieren
    for (uint8_t p : { PIN_DRV_EN, PIN_L_STEP, PIN_L_DIR,
                       PIN_R_STEP, PIN_R_DIR,
                       PIN_LIFT_EN,
                       PIN_LFT_R_STEP, PIN_LFT_R_DIR,
                       PIN_LFT_M_STEP, PIN_LFT_M_DIR,
                       PIN_LFT_L_STEP, PIN_LFT_L_DIR }) {
        pinMode(p, OUTPUT);
    }
    digitalWrite(PIN_DRV_EN,  LOW);   // Antrieb immer aktiv
    digitalWrite(PIN_LIFT_EN, LOW);   // Lift immer aktiv

    // Endstop-Pins (Input-Only, kein interner Pull-up auf GPIO 34-36!)
    pinMode(PIN_HOME_R, INPUT);
    pinMode(PIN_HOME_M, INPUT);
    pinMode(PIN_HOME_L, INPUT);

    // Geschwindigkeiten initialisieren
    drvL.setSpeed(DRIVE_SPEED_MM_S, STEPS_PER_MM);
    drvR.setSpeed(DRIVE_SPEED_MM_S, STEPS_PER_MM);
    lftR.setSpeed(LIFT_SPEED_MM_S,  LIFT_STEPS_PER_MM);
    lftM.setSpeed(LIFT_SPEED_MM_S,  LIFT_STEPS_PER_MM);
    lftL.setSpeed(LIFT_SPEED_MM_S,  LIFT_STEPS_PER_MM);

    Cmd cmd;
    while (true) {
        runLifts();

        // ST/RS direkt prüfen (höchste Priorität)
        if (stFlag) {
            stFlag = false;
            if (driveState == DS_RUNNING) driveState = DS_PAUSED;
            else if (driveState == DS_PAUSED) {
                // Zweites ST = Befehl abbrechen
                drvL.target = drvL.pos;
                drvR.target = drvR.pos;
                driveState = DS_IDLE;
            }
        }
        if (rsFlag) {
            rsFlag = false;
            if (driveState == DS_PAUSED) driveState = DS_RUNNING;
        }

        switch (driveState) {
            case DS_IDLE:
                if (xQueueReceive(cmdQ, &cmd, 0) == pdTRUE) {
                    if (cmd.type == C_DD) {
                        long steps = (long)(fabsf(cmd.a) * STEPS_PER_MM);
                        bool fwd = cmd.a >= 0;
                        drvL.setSpeed(DRIVE_SPEED_MM_S, STEPS_PER_MM);
                        drvR.setSpeed(DRIVE_SPEED_MM_S, STEPS_PER_MM);
                        drvL.pos = 0; drvL.target = fwd ?  steps : -steps;
                        drvR.pos = 0; drvR.target = fwd ? -steps :  steps; // R gespiegelt
                        driveState = DS_RUNNING;

                    } else if (cmd.type == C_TA) {
                        long steps = (long)(fabsf(cmd.a) * STEPS_PER_DEG);
                        bool cw = cmd.a >= 0;
                        drvL.setSpeed(TURN_SPEED_MM_S, STEPS_PER_MM);
                        drvR.setSpeed(TURN_SPEED_MM_S, STEPS_PER_MM);
                        // CW: L=+, R=+ (R gespiegelt → physisch rückwärts)
                        drvL.pos = 0; drvL.target = cw ?  steps : -steps;
                        drvR.pos = 0; drvR.target = cw ?  steps : -steps;
                        driveState = DS_RUNNING;

                    } else if (cmd.type == C_SL) {
                        lftR.target = (long)(cmd.a * LIFT_STEPS_PER_MM);
                        lftM.target = (long)(cmd.b * LIFT_STEPS_PER_MM);
                        lftL.target = (long)(cmd.c * LIFT_STEPS_PER_MM);
                        lftR.setSpeed(LIFT_SPEED_MM_S,  LIFT_STEPS_PER_MM);
                        lftM.setSpeed(LIFT_SPEED_MM_S,  LIFT_STEPS_PER_MM);
                        lftL.setSpeed(LIFT_SPEED_MM_S,  LIFT_STEPS_PER_MM);

                    } else if (cmd.type == C_SH) {
                        lftR.target = -999999; lftR.setSpeed(LIFT_HOME_SPEED_MM_S, LIFT_STEPS_PER_MM);
                        lftM.target = -999999; lftM.setSpeed(LIFT_HOME_SPEED_MM_S, LIFT_STEPS_PER_MM);
                        lftL.target = -999999; lftL.setSpeed(LIFT_HOME_SPEED_MM_S, LIFT_STEPS_PER_MM);
                        homeRdone = homeMdone = homeLdone = false;
                        liftHoming = true;
                    }
                }
                break;

            case DS_RUNNING: {
                bool lDone = drvL.atTarget();
                bool rDone = drvR.atTarget();
                if (!lDone) drvL.runOnce();
                if (!rDone) drvR.runOnce();
                if (lDone && rDone) {
                    driveState = DS_IDLE;
                    sendOK     = true;
                }
                break;
            }

            case DS_PAUSED:
                // warten auf RS oder zweites ST (oben behandelt)
                vTaskDelay(1);
                break;
        }

        // OK senden wenn fällig (Serial ist thread-safe auf ESP32)
        if (sendOK) {
            sendOK = false;
            Serial.println("OK");
        }
    }
}

// ═══════════════════════════════════════════════════════════════
//  UART-TASK  (Core 1)
// ═══════════════════════════════════════════════════════════════

static void parseCmd(const String &s) {
    Cmd cmd = {};

    if (s.startsWith("DD")) {
        cmd.type = C_DD;
        cmd.a    = s.substring(2).toFloat();
        xQueueSend(cmdQ, &cmd, portMAX_DELAY);

    } else if (s.startsWith("TA")) {
        cmd.type = C_TA;
        cmd.a    = s.substring(2).toFloat();
        xQueueSend(cmdQ, &cmd, portMAX_DELAY);

    } else if (s.startsWith("SL")) {
        // SL{r};{m};{l}
        int i1 = s.indexOf(';', 2);
        int i2 = (i1 >= 0) ? s.indexOf(';', i1 + 1) : -1;
        if (i1 < 0 || i2 < 0) { Serial.println("ERR"); return; }
        cmd.type = C_SL;
        cmd.a = s.substring(2,    i1).toFloat();
        cmd.b = s.substring(i1+1, i2).toFloat();
        cmd.c = s.substring(i2+1).toFloat();
        xQueueSend(cmdQ, &cmd, portMAX_DELAY);

    } else if (s == "SH") {
        cmd.type = C_SH;
        xQueueSend(cmdQ, &cmd, portMAX_DELAY);

    } else if (s == "ST") {
        stFlag = true;   // direktes Flag, kein Queue

    } else if (s == "RS") {
        rsFlag = true;   // direktes Flag, kein Queue

    } else if (s.startsWith("SP")) {
        // Nur Odometrie-Reset; ESP32 trackt keine eigene Odometrie
        // → kein OK senden (Raspi erwartet keines)

    } else {
        Serial.println("ERR");
    }
}

void uartTask(void *) {
    String buf = "";
    while (true) {
        while (Serial.available()) {
            char c = (char)Serial.read();
            if (c == '\n' || c == '\r') {
                buf.trim();
                if (buf.length() > 0) parseCmd(buf);
                buf = "";
            } else {
                buf += c;
            }
        }
        vTaskDelay(1 / portTICK_PERIOD_MS);
    }
}

// ═══════════════════════════════════════════════════════════════
//  SETUP & LOOP
// ═══════════════════════════════════════════════════════════════
void setup() {
    Serial.begin(115200);  // UART0 → USB → Raspberry Pi
    cmdQ = xQueueCreate(32, sizeof(Cmd));
    xTaskCreatePinnedToCore(motorTask, "Motor", 8192, NULL, 2, NULL, 0);  // Core 0, Prio 2
    xTaskCreatePinnedToCore(uartTask,  "UART",  4096, NULL, 1, NULL, 1);  // Core 1, Prio 1
}

void loop() {
    vTaskDelay(1000 / portTICK_PERIOD_MS);  // loop() wird nicht genutzt
}
