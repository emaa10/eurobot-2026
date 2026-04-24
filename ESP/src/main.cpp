/*
 * Eurobot 2026 – ESP32 Drive Controller
 *
 * Core 0: stepperTask  – AccelStepper, läuft durch ohne Delay
 * Core 1: uartTask     – Serial I/O → Command-Queue
 *
 * Raspi → ESP32:
 *   DD{mm}         Geradeaus  (+ vorwärts, – rückwärts)
 *   TA{deg}        Drehen     (+ im Uhrzeigersinn)
 *   HE             Endstop-Homing: rückwärts bis GPIO5 LOW, dann OK
 *   ST             Sofort stoppen (interrupt, kein Queue)
 *   RS             Weiterfahren nach ST
 *   SP{x};{y};{t}  Odometrie setzen (kein Ack)
 *
 * ESP32 → Raspi:
 *   OK             Befehl vollständig ausgeführt
 *   INTERRUPTED    Befehl durch ST abgebrochen
 *   ERR            Unbekannter Befehl
 */

#include <Arduino.h>
#include <AccelStepper.h>

// ── Pins ──────────────────────────────────────────────────────────────────
#define STEP_R       26
#define DIR_R        27
#define DIR_L        25
#define STEP_L       33
#define ENDSTOP_PIN   5   // INPUT_PULLUP: HIGH = offen, LOW = gedrückt

// ── Motor-Geometrie – AN HARDWARE ANPASSEN ───────────────────────────────
static constexpr float STEPS_PER_REV = 730.0f;
static constexpr float WHEEL_DIAM_MM = 48.0f;
static constexpr float WHEELBASE_MM  = 226.0f;
static constexpr float STEPS_PER_MM  = STEPS_PER_REV / (WHEEL_DIAM_MM * PI);
static constexpr float STEPS_PER_DEG = WHEELBASE_MM * PI / 360.0f * STEPS_PER_MM;
static constexpr float MAX_SPEED_R   = 1500.0f;
static constexpr float MAX_SPEED_L   = 1465.0f;  // 2.3% langsamer → Rechtsdrall korrigieren
static constexpr float ACCEL         = 1200.0f;  // steps/s²
static constexpr float HOMING_SPEED  = 400.0f;   // steps/s – langsam an Wand heranfahren

// ── AccelStepper ──────────────────────────────────────────────────────────
AccelStepper stepperR(AccelStepper::DRIVER, STEP_R, DIR_R);
AccelStepper stepperL(AccelStepper::DRIVER, STEP_L, DIR_L);

// ── Command queue ─────────────────────────────────────────────────────────
struct Cmd { char type; int32_t val; };  // type: 'D'=DD, 'T'=TA, 'H'=HE
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
//  IDLE ──DD/TA──► MOVING ──ST──► STOPPING ──stillstand──► PAUSED
//                                                              │
//                  ◄─────────────────── RS ───────────────────┘
//  PAUSED ──ST──► IDLE  (sendet INTERRUPTED)
//
//  IDLE ──HE──► HOMING ──endstop LOW──► HOMING_STOP ──stillstand──► IDLE (OK)
//
enum class MotionState { IDLE, MOVING, STOPPING, PAUSED, HOMING, HOMING_STOP };

static long savedTargetR = 0, savedTargetL = 0;
static long homingStartPosR = 0;
static constexpr long MIN_HOMING_STEPS = 100;  // ~20mm Anti-Bounce vor Endstop-Check

static void stepperTask(void*) {
    MotionState state = MotionState::IDLE;
    Cmd cmd = {};

    while (true) {
        TickType_t wait = (state == MotionState::IDLE) ? portMAX_DELAY : 0;
        if (xQueueReceive(cmdQueue, &cmd, wait) == pdTRUE) {
            if (state == MotionState::IDLE) {
                if (cmd.type == 'D') {
                    long s = lroundf(cmd.val * STEPS_PER_MM);
                    stepperR.move(s);
                    stepperL.move(lroundf(s * MAX_SPEED_L / MAX_SPEED_R));
                    state = MotionState::MOVING;
                } else if (cmd.type == 'T') {
                    long s = lroundf(cmd.val * STEPS_PER_DEG);
                    stepperR.move(-s);
                    stepperL.move(lroundf(s * MAX_SPEED_L / MAX_SPEED_R));
                    state = MotionState::MOVING;
                } else if (cmd.type == 'H') {
                    // Langsam rückwärts bis Endstop – Pin-Status zuerst senden
                    serialPrintln(digitalRead(ENDSTOP_PIN) == LOW ? "ES:LOW" : "ES:HIGH");
                    stepperR.setMaxSpeed(HOMING_SPEED);
                    stepperL.setMaxSpeed(HOMING_SPEED * MAX_SPEED_L / MAX_SPEED_R);
                    stepperR.move(-100000L);
                    stepperL.move(lroundf(-100000.0f * MAX_SPEED_L / MAX_SPEED_R));
                    homingStartPosR = stepperR.currentPosition();
                    state = MotionState::HOMING;
                }
            }
        }

        if (stopFlag) {
            stopFlag = false;
            if (state == MotionState::MOVING) {
                savedTargetR = stepperR.targetPosition();
                savedTargetL = stepperL.targetPosition();
                stepperR.stop();
                stepperL.stop();
                state = MotionState::STOPPING;
            } else if (state == MotionState::PAUSED) {
                state = MotionState::IDLE;
                serialPrintln("INTERRUPTED");
            }
        }

        if (resumeFlag) {
            resumeFlag = false;
            if (state == MotionState::PAUSED) {
                long remR = savedTargetR - stepperR.currentPosition();
                long remL = savedTargetL - stepperL.currentPosition();
                stepperR.move(remR);
                stepperL.move(remL);
                state = MotionState::MOVING;
            }
        }

        if (state == MotionState::MOVING || state == MotionState::STOPPING) {
            stepperR.run();
            stepperL.run();
            if (!stepperR.isRunning() && !stepperL.isRunning()) {
                if (state == MotionState::STOPPING) {
                    state = MotionState::PAUSED;
                } else {
                    state = MotionState::IDLE;
                    serialPrintln("OK");
                }
            }
        }

        if (state == MotionState::HOMING) {
            stepperR.run();
            stepperL.run();
            bool travelledEnough = abs(stepperR.currentPosition() - homingStartPosR) >= MIN_HOMING_STEPS;
            if (travelledEnough && digitalRead(ENDSTOP_PIN) == LOW) {
                stepperR.stop();
                stepperL.stop();
                state = MotionState::HOMING_STOP;
            }
        }

        if (state == MotionState::HOMING_STOP) {
            stepperR.run();
            stepperL.run();
            if (!stepperR.isRunning() && !stepperL.isRunning()) {
                stepperR.setMaxSpeed(MAX_SPEED_R);
                stepperL.setMaxSpeed(MAX_SPEED_L);
                state = MotionState::IDLE;
                serialPrintln("OK");
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
                    } else if (buf == "ES") {
                        // Debug: Endstop-Status zurückmelden
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
                        // Odometrie-Sync – kein Ack nötig
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

    pinMode(ENDSTOP_PIN, INPUT_PULLUP);

    stepperR.setMaxSpeed(MAX_SPEED_R);
    stepperR.setAcceleration(ACCEL * (MAX_SPEED_R / MAX_SPEED_L));
    stepperL.setMaxSpeed(MAX_SPEED_L);
    stepperL.setAcceleration(ACCEL);
    stepperL.setPinsInverted(true, false, false);

    cmdQueue  = xQueueCreate(8, sizeof(Cmd));
    serialMtx = xSemaphoreCreateMutex();

    xTaskCreatePinnedToCore(stepperTask, "stepper", 4096, nullptr, 2, nullptr, 0);
    xTaskCreatePinnedToCore(uartTask,   "uart",    4096, nullptr, 1, nullptr, 1);
}

void loop() {
    vTaskDelay(portMAX_DELAY);
}
