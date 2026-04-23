/*
 * Eurobot 2026 – ESP32 Drive Controller
 * Fahrbasis: 2 Stepper-Motoren (Differentialantrieb)
 *
 * Protokoll (Raspi → ESP32, newline-terminated):
 *   DD{mm}         Geradeaus fahren (+ vorwärts, – rückwärts)
 *   TA{deg}        Drehen um relativen Winkel (+ im Uhrzeigersinn)
 *   ST             Antrieb pausieren (Hinderniserkennung)
 *   RS             Antrieb fortsetzen nach ST
 *   SP{x};{y};{t}  Odometrie-Position setzen (kein OK)
 *
 * ESP32 → Raspi:
 *   OK             DD / TA abgeschlossen
 *   ERR            Ungültiger Befehl
 */

#include <Arduino.h>

// ═══════════════════════════════════════════════════════════
//  PINOUT  (!! AN ECHTE HARDWARE ANPASSEN !!)
// ═══════════════════════════════════════════════════════════

#define PIN_DRV_EN   27   // Enable, aktiv LOW (shared)
#define PIN_L_STEP   25   // Linker Motor STEP
#define PIN_L_DIR    26   // Linker Motor DIR   (HIGH = vorwärts)
#define PIN_R_STEP   32   // Rechter Motor STEP
#define PIN_R_DIR    33   // Rechter Motor DIR  (LOW = vorwärts, Motor gespiegelt)

// ═══════════════════════════════════════════════════════════
//  MECHANIK  (!! AN ECHTE HARDWARE ANPASSEN !!)
// ═══════════════════════════════════════════════════════════

#define STEPS_PER_REV   3200      // inkl. Microstepping (z.B. 200 × 16)
#define WHEEL_DIAM_MM   65.0f     // Raddurchmesser in mm
#define WHEELBASE_MM   220.0f     // Radabstand Kontaktpunkte in mm
#define DRIVE_SPEED_MM_S 150.0f   // Fahrgeschwindigkeit mm/s
#define TURN_SPEED_MM_S  100.0f   // Drehgeschwindigkeit (Tangential) mm/s

// ═══════════════════════════════════════════════════════════
//  ABGELEITETE KONSTANTEN
// ═══════════════════════════════════════════════════════════
static const float STEPS_PER_MM  = STEPS_PER_REV / (PI * WHEEL_DIAM_MM);
static const float STEPS_PER_DEG = WHEELBASE_MM * PI / 360.0f * STEPS_PER_MM;

static uint32_t mmPerStoUs(float mmS) {
    if (mmS <= 0.0f) return 5000;
    return (uint32_t)(1000000.0f / (mmS * STEPS_PER_MM));
}

// ═══════════════════════════════════════════════════════════
//  STEPPER-HILFSSTRUKTUR
// ═══════════════════════════════════════════════════════════
struct Stepper {
    uint8_t  stepPin, dirPin;
    volatile long    pos    = 0;
    volatile long    target = 0;
    uint32_t intervalUs     = 1000;
    uint32_t nextUs         = 0;

    void setIntervalUs(uint32_t us) { intervalUs = us; }

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
};

// ═══════════════════════════════════════════════════════════
//  GLOBALER ZUSTAND
// ═══════════════════════════════════════════════════════════
Stepper drvL = { PIN_L_STEP, PIN_L_DIR };
Stepper drvR = { PIN_R_STEP, PIN_R_DIR };

enum DriveState : uint8_t { DS_IDLE, DS_RUNNING, DS_PAUSED };
volatile DriveState driveState = DS_IDLE;
volatile bool       sendOK     = false;

// ST/RS als Direktflags – zeitkritisch, bypasst Queue
volatile bool stFlag = false;
volatile bool rsFlag = false;

enum CmdType : uint8_t { C_DD, C_TA };
struct Cmd { CmdType type; float val; };
QueueHandle_t cmdQ;

// ═══════════════════════════════════════════════════════════
//  MOTOR-TASK  (Core 0)
// ═══════════════════════════════════════════════════════════
void motorTask(void *) {
    pinMode(PIN_DRV_EN, OUTPUT);
    pinMode(PIN_L_STEP, OUTPUT); pinMode(PIN_L_DIR, OUTPUT);
    pinMode(PIN_R_STEP, OUTPUT); pinMode(PIN_R_DIR, OUTPUT);
    digitalWrite(PIN_DRV_EN, LOW);   // Treiber aktiv

    Cmd cmd;
    while (true) {
        // ST / RS direkt prüfen
        if (stFlag) {
            stFlag = false;
            if      (driveState == DS_RUNNING) driveState = DS_PAUSED;
            else if (driveState == DS_PAUSED) {
                // zweites ST = Befehl abbrechen
                drvL.target = drvL.pos;
                drvR.target = drvR.pos;
                driveState  = DS_IDLE;
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
                        long steps = (long)(fabsf(cmd.val) * STEPS_PER_MM);
                        bool fwd = cmd.val >= 0;
                        drvL.setIntervalUs(mmPerStoUs(DRIVE_SPEED_MM_S));
                        drvR.setIntervalUs(mmPerStoUs(DRIVE_SPEED_MM_S));
                        drvL.pos = 0; drvL.target = fwd ?  steps : -steps;
                        drvR.pos = 0; drvR.target = fwd ? -steps :  steps; // R gespiegelt
                    } else {  // C_TA
                        long steps = (long)(fabsf(cmd.val) * STEPS_PER_DEG);
                        bool cw = cmd.val >= 0;
                        drvL.setIntervalUs(mmPerStoUs(TURN_SPEED_MM_S));
                        drvR.setIntervalUs(mmPerStoUs(TURN_SPEED_MM_S));
                        // CW: L=+, R=+ (R gespiegelt → physisch rückwärts)
                        drvL.pos = 0; drvL.target = cw ?  steps : -steps;
                        drvR.pos = 0; drvR.target = cw ?  steps : -steps;
                    }
                    driveState = DS_RUNNING;
                }
                break;

            case DS_RUNNING:
                if (!drvL.atTarget()) drvL.runOnce();
                if (!drvR.atTarget()) drvR.runOnce();
                if (drvL.atTarget() && drvR.atTarget()) {
                    driveState = DS_IDLE;
                    sendOK     = true;
                }
                break;

            case DS_PAUSED:
                vTaskDelay(1);
                break;
        }

        if (sendOK) {
            sendOK = false;
            Serial.println("OK");
        }
    }
}

// ═══════════════════════════════════════════════════════════
//  UART-TASK  (Core 1)
// ═══════════════════════════════════════════════════════════
static void parseCmd(const String &s) {
    Cmd cmd = {};
    if (s.startsWith("DD")) {
        cmd.type = C_DD;
        cmd.val  = s.substring(2).toFloat();
        xQueueSend(cmdQ, &cmd, portMAX_DELAY);

    } else if (s.startsWith("TA")) {
        cmd.type = C_TA;
        cmd.val  = s.substring(2).toFloat();
        xQueueSend(cmdQ, &cmd, portMAX_DELAY);

    } else if (s == "ST") {
        stFlag = true;

    } else if (s == "RS") {
        rsFlag = true;

    } else if (s.startsWith("SP")) {
        // Odometrie-Reset – nur Raspi-seitig relevant, kein OK

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

// ═══════════════════════════════════════════════════════════
//  SETUP & LOOP
// ═══════════════════════════════════════════════════════════
void setup() {
    Serial.begin(115200);
    cmdQ = xQueueCreate(32, sizeof(Cmd));
    xTaskCreatePinnedToCore(motorTask, "Motor", 4096, NULL, 2, NULL, 0);
    xTaskCreatePinnedToCore(uartTask,  "UART",  4096, NULL, 1, NULL, 1);
}

void loop() {
    vTaskDelay(1000 / portTICK_PERIOD_MS);
}
