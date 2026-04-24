/*
 * Eurobot 2026 – ESP32 Drive Controller
 *
 * Core 0: stepperTask  – AccelStepper, läuft durch ohne Delay
 * Core 1: uartTask     – Serial I/O → Command-Queue
 *
 * Raspi → ESP32:
 *   DD{mm}         Geradeaus  (+ vorwärts, – rückwärts)
 *   TA{deg}        Drehen     (+ im Uhrzeigersinn)
 *   ST             Sofort stoppen (interrupt, kein Queue)
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
#define STEP_R 26
#define DIR_R  27
#define DIR_L  25
#define STEP_L 33

// ── Motor-Geometrie – AN HARDWARE ANPASSEN ───────────────────────────────
// Falls Roboter falsch dreht/fährt: INVERT_L oder INVERT_R togglen.
// Falls Distanz/Winkel falsch: WHEEL_DIAM_MM bzw. WHEELBASE_MM anpassen.
static constexpr float STEPS_PER_REV = 3200.0f;  // 200 Schritte × 16 Microsteps (TB6600)
static constexpr float WHEEL_DIAM_MM = 60.0f;
static constexpr float WHEELBASE_MM  = 200.0f;
static constexpr float STEPS_PER_MM  = STEPS_PER_REV / (WHEEL_DIAM_MM * PI);
static constexpr float STEPS_PER_DEG = WHEELBASE_MM * PI / 360.0f * STEPS_PER_MM;
static constexpr float MAX_SPEED     = 1500.0f;  // steps/s
static constexpr float ACCEL         = 1200.0f;  // steps/s²

// ── AccelStepper ──────────────────────────────────────────────────────────
AccelStepper stepperR(AccelStepper::DRIVER, STEP_R, DIR_R);
AccelStepper stepperL(AccelStepper::DRIVER, STEP_L, DIR_L);

// ── Command queue ─────────────────────────────────────────────────────────
struct Cmd { char type; int32_t val; };  // type: 'D'=DD, 'T'=TA
static QueueHandle_t cmdQueue;

// ── Shared ────────────────────────────────────────────────────────────────
static SemaphoreHandle_t serialMtx;
static volatile bool stopFlag = false;

static void serialPrintln(const char* msg) {
    if (xSemaphoreTake(serialMtx, pdMS_TO_TICKS(50)) == pdTRUE) {
        Serial.println(msg);
        Serial.flush();
        xSemaphoreGive(serialMtx);
    }
}

// ── Core 0: Stepper-Task ──────────────────────────────────────────────────
enum class MotionState { IDLE, MOVING, STOPPING };

static void stepperTask(void*) {
    MotionState state = MotionState::IDLE;
    Cmd cmd = {};

    while (true) {
        // Blockiert im IDLE, poll im MOVING/STOPPING
        TickType_t wait = (state == MotionState::IDLE) ? portMAX_DELAY : 0;
        if (xQueueReceive(cmdQueue, &cmd, wait) == pdTRUE) {
            if (state == MotionState::IDLE) {
                if (cmd.type == 'D') {
                    long s = lroundf(cmd.val * STEPS_PER_MM);
                    stepperR.move(s);
                    stepperL.move(s);   // gleiche Richtung, gleiche Montage
                    state = MotionState::MOVING;
                } else if (cmd.type == 'T') {
                    long s = lroundf(cmd.val * STEPS_PER_DEG);
                    // CW (+deg): R rückwärts, L vorwärts
                    stepperR.move(-s);
                    stepperL.move(s);
                    state = MotionState::MOVING;
                }
            }
            // Neue DD/TA während MOVING → ignoriert (Raspi wartet auf OK/INTERRUPTED)
        }

        // ST-Flag: interrupt laufende Bewegung
        if (state == MotionState::MOVING && stopFlag) {
            stopFlag = false;
            stepperR.stop();
            stepperL.stop();
            state = MotionState::STOPPING;
        }

        if (state != MotionState::IDLE) {
            stepperR.run();
            stepperL.run();
            if (!stepperR.isRunning() && !stepperL.isRunning()) {
                bool interrupted = (state == MotionState::STOPPING);
                state = MotionState::IDLE;
                serialPrintln(interrupted ? "INTERRUPTED" : "OK");
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
                if (buf.length() > 64) buf = "";  // Overflow-Schutz
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

// ── Setup / Loop ──────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    disableCore0WDT();  // stepperTask läuft als Tight-Loop auf Core 0 ohne yield

    stepperR.setMaxSpeed(MAX_SPEED);
    stepperR.setAcceleration(ACCEL);
    stepperL.setMaxSpeed(MAX_SPEED);
    stepperL.setAcceleration(ACCEL);
    stepperL.setPinsInverted(true, false, false);  // DIR_L invertieren

    cmdQueue  = xQueueCreate(8, sizeof(Cmd));
    serialMtx = xSemaphoreCreateMutex();

    xTaskCreatePinnedToCore(stepperTask, "stepper", 4096, nullptr, 2, nullptr, 0);
    xTaskCreatePinnedToCore(uartTask,   "uart",    4096, nullptr, 1, nullptr, 1);
}

void loop() {
    vTaskDelay(portMAX_DELAY);  // Arduino-Loop ceded, alles in FreeRTOS-Tasks
}
