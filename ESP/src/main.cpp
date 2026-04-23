/*
 * Eurobot 2026 – ESP32 Drive Controller
 * Basis: Christophs doSteps-Architektur (dual-core FreeRTOS)
 * Protokoll auf DD/TA/ST/RS/SP angepasst (mm / Grad)
 *
 * Raspi → ESP32:
 *   DD{mm}         Geradeaus  (+ vorwärts, – rückwärts)
 *   TA{deg}        Drehen     (+ im Uhrzeigersinn)
 *   ST             Sofort stoppen, aktuellen Befehl abbrechen
 *   RS             (reserviert, kein aktives Resume – neuer Befehl nötig)
 *   SP{x};{y};{t}  Odometrie setzen (kein OK, nur Raspi-intern)
 *
 * ESP32 → Raspi:
 *   OK             Befehl vollständig ausgeführt
 *   INTERRUPTED    Befehl durch ST abgebrochen
 *   ERR            Unbekannter Befehl
 */

#include <Arduino.h>

// ═══════════════════════════════════════════════════════════
//  PINS
// ═══════════════════════════════════════════════════════════
#define STEP_L  25
#define DIR_L   26
#define STEP_R  32
#define DIR_R   33
// Kein separater Enable-Pin nötig wenn Treiber permanent aktiv

// ═══════════════════════════════════════════════════════════
//  MECHANIK  – Christophs Hardware-Parameter
// ═══════════════════════════════════════════════════════════
#define STEPS_PER_REV   200       // Vollschritt (kein Microstepping)
#define WHEEL_DIAM_MM   65.0f     // Raddurchmesser mm
#define WHEELBASE_MM   150.0f     // Radabstand mm  (Christoph: 15 cm)
#define DRIVE_SPEED_CM_S 10.0f    // Standard-Fahrgeschwindigkeit cm/s

static const float STEPS_PER_MM = STEPS_PER_REV / (PI * WHEEL_DIAM_MM);
static const float STEPS_PER_CM = STEPS_PER_REV / (PI * WHEEL_DIAM_MM * 0.1f);

// cm/s → halbe Periodendauer µs (Christophs Formel)
static int toDelayUs(float cmS) {
    if (cmS <= 0.0f) return 5000;
    int d = (int)(500000.0f / (cmS * STEPS_PER_CM));
    return max(d, 100);
}

// ═══════════════════════════════════════════════════════════
//  SHARED STATE
// ═══════════════════════════════════════════════════════════
portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
volatile bool  stopFlag = false;
volatile long  posL = 0, posR = 0;   // steps, vorwärts positiv
volatile float spdL = DRIVE_SPEED_CM_S;
volatile float spdR = DRIVE_SPEED_CM_S;

// ═══════════════════════════════════════════════════════════
//  COMMAND QUEUE
// ═══════════════════════════════════════════════════════════
enum CmdType : uint8_t { CMD_DRIVE, CMD_TURN };
struct Cmd { CmdType type; float val; };
QueueHandle_t cmdQueue;

// ═══════════════════════════════════════════════════════════
//  STEPPER-KERN (Christophs doSteps)
//  dirL/dirR: HIGH oder LOW  |  R ist gespiegelt montiert
//  Rückgabe false = durch ST unterbrochen
// ═══════════════════════════════════════════════════════════
static bool doSteps(uint8_t dirL, uint8_t dirR, long stepsL, long stepsR) {
    digitalWrite(DIR_L, dirL);
    digitalWrite(DIR_R, dirR);

    int dL = toDelayUs(spdL);
    int dR = toDelayUs(spdR);
    long doneL = 0, doneR = 0;
    unsigned long nextL = micros(), nextR = micros();

    while (doneL < stepsL || doneR < stepsR) {
        if (stopFlag) return false;
        unsigned long now = micros();

        if (doneL < stepsL && (long)(now - nextL) >= 0) {
            digitalWrite(STEP_L, HIGH); delayMicroseconds(5); digitalWrite(STEP_L, LOW);
            nextL = now + (unsigned long)(dL * 2);
            portENTER_CRITICAL(&mux);
            posL += (dirL == HIGH) ? 1 : -1;
            portEXIT_CRITICAL(&mux);
            doneL++;
        }
        if (doneR < stepsR && (long)(now - nextR) >= 0) {
            digitalWrite(STEP_R, HIGH); delayMicroseconds(5); digitalWrite(STEP_R, LOW);
            nextR = now + (unsigned long)(dR * 2);
            portENTER_CRITICAL(&mux);
            posR += (dirR == LOW) ? 1 : -1;   // R gespiegelt: LOW = vorwärts
            portEXIT_CRITICAL(&mux);
            doneR++;
        }
    }
    return true;
}

// ═══════════════════════════════════════════════════════════
//  STEPPER-TASK  (Core 0)
// ═══════════════════════════════════════════════════════════
void stepperTask(void *) {
    pinMode(STEP_L, OUTPUT); pinMode(DIR_L, OUTPUT);
    pinMode(STEP_R, OUTPUT); pinMode(DIR_R, OUTPUT);

    Cmd cmd;
    while (true) {
        if (xQueueReceive(cmdQueue, &cmd, portMAX_DELAY) != pdTRUE) continue;
        stopFlag = false;

        bool ok;
        if (cmd.type == CMD_DRIVE) {
            long steps = (long)(fabsf(cmd.val) * STEPS_PER_MM);
            bool fwd = cmd.val >= 0;
            // vorwärts: L=HIGH, R=LOW (gespiegelt)
            ok = doSteps(fwd ? HIGH : LOW, fwd ? LOW : HIGH, steps, steps);

        } else {  // CMD_TURN
            // Bogen pro Rad = Radabstand × π × |deg| / 360
            float arc_mm = fabsf(cmd.val) / 360.0f * PI * WHEELBASE_MM;
            long steps = (long)(arc_mm * STEPS_PER_MM);
            bool cw = cmd.val >= 0;
            // CW: L vorwärts (HIGH), R vorwärts gespiegelt (HIGH)
            ok = doSteps(cw ? HIGH : LOW, cw ? HIGH : LOW, steps, steps);
        }

        Serial.println(ok ? "OK" : "INTERRUPTED");
    }
}

// ═══════════════════════════════════════════════════════════
//  UART-TASK  (Core 1)
// ═══════════════════════════════════════════════════════════
static void parseCmd(const String &s) {
    Cmd cmd = {};

    if (s.startsWith("DD")) {
        cmd.type = CMD_DRIVE;
        cmd.val  = s.substring(2).toFloat();   // mm
        xQueueSend(cmdQueue, &cmd, 0);

    } else if (s.startsWith("TA")) {
        cmd.type = CMD_TURN;
        cmd.val  = s.substring(2).toFloat();   // Grad
        xQueueSend(cmdQueue, &cmd, 0);

    } else if (s == "ST") {
        stopFlag = true;
        xQueueReset(cmdQueue);
        // kein OK – INTERRUPTED kommt vom stepperTask

    } else if (s == "RS") {
        // Nach ST muss ein neuer DD/TA-Befehl kommen; RS ist hier no-op
        (void)0;

    } else if (s.startsWith("SP")) {
        // Odometrie-Reset – nur Raspi-intern, kein OK

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
    cmdQueue = xQueueCreate(16, sizeof(Cmd));
    xTaskCreatePinnedToCore(stepperTask, "Stepper", 4096, NULL, 2, NULL, 0);
    xTaskCreatePinnedToCore(uartTask,    "UART",    4096, NULL, 1, NULL, 1);
}

void loop() {
    vTaskDelay(1000 / portTICK_PERIOD_MS);
}
