/*
 * Eurobot 2026 – ESP32 Drive Controller
 *
 * Core 0: stepperTask  – direct GPIO stepping (wie Testcode, delayMicroseconds)
 * Core 1: uartTask     – Serial I/O → Command-Queue
 *
 * Raspi → ESP32:
 *   DD{mm}         Geradeaus  (+ vorwärts, – rückwärts)
 *   TA{deg}        Drehen     (+ im Uhrzeigersinn)
 *   HE             Endstop-Homing: rückwärts bis GPIO5 LOW, dann OK
 *   ST             Sofort stoppen (interrupt, kein Queue)
 *   RS             Weiterfahren nach ST
 *   MD             Motoren deaktivieren (EN HIGH) – vor Pullcord
 *   ME             Motoren aktivieren   (EN LOW)  – nach Pullcord
 *   SP{x};{y};{t}  Odometrie setzen (kein Ack)
 *
 * ESP32 → Raspi:
 *   OK             Befehl vollständig ausgeführt
 *   INTERRUPTED    Befehl durch ST abgebrochen
 *   ERR            Unbekannter Befehl
 */

#include <Arduino.h>

// ── Pins ──────────────────────────────────────────────────────────────────
#define STEP_R       26
#define DIR_R        27
#define DIR_L        25
#define STEP_L       33
#define EN_L         32
#define EN_R         35
#define ENDSTOP_PIN   5

// ── Motor-Geometrie ────────────────────────────────────────────────────────
// Motor-Invertierung: auf true setzen wenn Kabel am Treiber vertauscht
static constexpr bool  INVERT_R        = false;
static constexpr bool  INVERT_L        = false;

static constexpr float STEPS_PER_REV   = 1600.0f;
static constexpr float WHEEL_DIAM_MM   = 48.0f;
static constexpr float WHEELBASE_MM    = 226.0f;
static constexpr float STEPS_PER_MM    = STEPS_PER_REV / (WHEEL_DIAM_MM * PI);
static constexpr float STEPS_PER_DEG   = WHEELBASE_MM * PI / 360.0f * STEPS_PER_MM;
static constexpr int   STEP_DELAY_MIN  = 200;   // µs Vollgas
static constexpr int   STEP_DELAY_MAX  = 800;   // µs Anlauf/Auslauf
static constexpr long  ACCEL_STEPS     = 300;   // Rampenlänge in Steps
static constexpr long  MIN_HOMING_STEPS = 100;

// ── Command queue ─────────────────────────────────────────────────────────
struct Cmd { char type; int32_t val; };
static QueueHandle_t cmdQueue;

// ── Shared ────────────────────────────────────────────────────────────────
static SemaphoreHandle_t serialMtx;
static volatile bool stopFlag   = false;
static volatile bool resumeFlag = false;

static void serialPrintln(const char* msg) {
    if (xSemaphoreTake(serialMtx, pdMS_TO_TICKS(50)) == pdTRUE) {
        Serial.println(msg);
        Serial.flush();
        xSemaphoreGive(serialMtx);
    }
}

// ── Core 0: Stepper-Task ──────────────────────────────────────────────────
//
//  Vorwärts (DD+): DIR_R=LOW,  DIR_L=LOW
//  Rückwärts (DD-): DIR_R=HIGH, DIR_L=HIGH
//  Uhrzeigersinn (TA+): DIR_R=HIGH (zurück), DIR_L=LOW (vor)
//  Gegenuhrzeigersinn (TA-): DIR_R=LOW (vor),  DIR_L=HIGH (zurück)
//
enum class MotionState { IDLE, MOVING, PAUSED, HOMING };

static inline uint8_t dirR(uint8_t d) { return INVERT_R ? (d == HIGH ? LOW : HIGH) : d; }
static inline uint8_t dirL(uint8_t d) { return INVERT_L ? (d == HIGH ? LOW : HIGH) : d; }

static inline int accel_delay(long done, long rem) {
    long ramp = min(done, min(rem, ACCEL_STEPS));
    return STEP_DELAY_MAX - (int)((STEP_DELAY_MAX - STEP_DELAY_MIN) * ramp / ACCEL_STEPS);
}

static void stepperTask(void*) {
    MotionState state = MotionState::IDLE;
    long  stepsRem    = 0;
    long  totalSteps  = 0;
    long  homingSteps = 0;
    uint8_t savedDirR = LOW, savedDirL = LOW;
    Cmd cmd = {};

    while (true) {

        // ── IDLE ──────────────────────────────────────────────────────
        if (state == MotionState::IDLE) {
            if (xQueueReceive(cmdQueue, &cmd, portMAX_DELAY) != pdTRUE) continue;

            if (cmd.type == 'D') {
                // R: LOW=vor, HIGH=zurück  |  L: HIGH=vor, LOW=zurück
                long s = lroundf(cmd.val * STEPS_PER_MM);
                savedDirR = dirR((s >= 0) ? LOW  : HIGH);
                savedDirL = dirL((s >= 0) ? HIGH : LOW);
                totalSteps = stepsRem = abs(s);
                digitalWrite(DIR_R, savedDirR);
                digitalWrite(DIR_L, savedDirL);
                state = MotionState::MOVING;

            } else if (cmd.type == 'T') {
                // CW: R zurück (HIGH) + L vor (HIGH) = beide HIGH
                long s = lroundf(cmd.val * STEPS_PER_DEG);
                savedDirR = dirR((s >= 0) ? HIGH : LOW);
                savedDirL = dirL((s >= 0) ? HIGH : LOW);
                totalSteps = stepsRem = abs(s);
                digitalWrite(DIR_R, savedDirR);
                digitalWrite(DIR_L, savedDirL);
                state = MotionState::MOVING;

            } else if (cmd.type == 'H') {
                serialPrintln(digitalRead(ENDSTOP_PIN) == LOW ? "ES:LOW" : "ES:HIGH");
                digitalWrite(DIR_R, dirR(HIGH));
                digitalWrite(DIR_L, dirL(LOW));
                homingSteps = 0;
                state = MotionState::HOMING;
            }
        }

        // ── MOVING ────────────────────────────────────────────────────
        else if (state == MotionState::MOVING) {
            if (stopFlag) {
                stopFlag = false;
                state = MotionState::PAUSED;
            } else if (stepsRem <= 0) {
                state = MotionState::IDLE;
                serialPrintln("OK");
            } else {
                int d = accel_delay(totalSteps - stepsRem, stepsRem);
                digitalWrite(STEP_R, HIGH);
                digitalWrite(STEP_L, HIGH);
                delayMicroseconds(d);
                digitalWrite(STEP_R, LOW);
                digitalWrite(STEP_L, LOW);
                delayMicroseconds(d);
                stepsRem--;
            }
        }

        // ── PAUSED ────────────────────────────────────────────────────
        else if (state == MotionState::PAUSED) {
            if (resumeFlag) {
                resumeFlag = false;
                totalSteps = stepsRem;  // Rampe neu starten
                digitalWrite(DIR_R, savedDirR);
                digitalWrite(DIR_L, savedDirL);
                state = MotionState::MOVING;
            } else if (stopFlag) {
                stopFlag = false;
                stepsRem = 0;
                state = MotionState::IDLE;
                serialPrintln("INTERRUPTED");
            } else {
                vTaskDelay(pdMS_TO_TICKS(1));
            }
        }

        // ── HOMING ────────────────────────────────────────────────────
        else if (state == MotionState::HOMING) {
            if (stopFlag) {
                stopFlag = false;
                state = MotionState::IDLE;
                serialPrintln("INTERRUPTED");
            } else if (homingSteps >= MIN_HOMING_STEPS && digitalRead(ENDSTOP_PIN) == LOW) {
                state = MotionState::IDLE;
                serialPrintln("OK");
            } else {
                digitalWrite(STEP_R, HIGH);
                digitalWrite(STEP_L, HIGH);
                delayMicroseconds(STEP_DELAY_MAX);
                digitalWrite(STEP_R, LOW);
                digitalWrite(STEP_L, LOW);
                delayMicroseconds(STEP_DELAY_MAX);
                homingSteps++;
            }
        }
    }
}

// ── Core 1: UART-Task ─────────────────────────────────────────────────────
static void uartTask(void*) {
    String buf;
    buf.reserve(32);

    while (true) {
        while (Serial.available()) {
            char c = (char)Serial.read();
            if (c == '\n' || c == '\r') {
                buf.trim();
                if (buf.length() >= 2) {
                    Cmd cmd = {};
                    if (buf == "ST") {
                        stopFlag = true;
                    } else if (buf == "RS") {
                        resumeFlag = true;
                    } else if (buf == "MD") {
                        stopFlag = true;
                        digitalWrite(EN_L, HIGH);
                        digitalWrite(EN_R, HIGH);
                        serialPrintln("OK");
                    } else if (buf == "ME") {
                        digitalWrite(EN_L, LOW);
                        digitalWrite(EN_R, LOW);
                        serialPrintln("OK");
                    } else if (buf == "ES") {
                        serialPrintln(digitalRead(ENDSTOP_PIN) == LOW ? "ENDSTOP:LOW" : "ENDSTOP:HIGH");
                    } else if (buf == "HE") {
                        cmd.type = 'H';
                        stopFlag = false;
                        xQueueSend(cmdQueue, &cmd, pdMS_TO_TICKS(200));
                    } else if (buf.startsWith("DD")) {
                        cmd.type = 'D';
                        cmd.val  = (int32_t)buf.substring(2).toInt();
                        stopFlag = false;
                        xQueueSend(cmdQueue, &cmd, pdMS_TO_TICKS(200));
                    } else if (buf.startsWith("TA")) {
                        cmd.type = 'T';
                        cmd.val  = (int32_t)buf.substring(2).toInt();
                        stopFlag = false;
                        xQueueSend(cmdQueue, &cmd, pdMS_TO_TICKS(200));
                    } else if (buf.startsWith("SP")) {
                        // Odometrie-Sync – kein Ack
                    } else {
                        serialPrintln("ERR");
                    }
                    buf = "";
                }
            } else if (c != '\r') {
                buf += c;
                if (buf.length() > 64) buf = "";
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

// ── Setup / Loop ──────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    disableCore0WDT();

    pinMode(STEP_R, OUTPUT);
    pinMode(DIR_R,  OUTPUT);
    pinMode(STEP_L, OUTPUT);
    pinMode(DIR_L,  OUTPUT);
    pinMode(EN_L,   OUTPUT);
    pinMode(EN_R,   OUTPUT);

    digitalWrite(EN_L, HIGH);  // deaktiviert bis ME-Befehl (nach Pullcord)
    digitalWrite(EN_R, HIGH);

    pinMode(ENDSTOP_PIN, INPUT_PULLUP);

    cmdQueue  = xQueueCreate(8, sizeof(Cmd));
    serialMtx = xSemaphoreCreateMutex();

    xTaskCreatePinnedToCore(stepperTask, "stepper", 4096, nullptr, 2, nullptr, 0);
    xTaskCreatePinnedToCore(uartTask,   "uart",    4096, nullptr, 1, nullptr, 1);
}

void loop() {
    vTaskDelay(portMAX_DELAY);
}
