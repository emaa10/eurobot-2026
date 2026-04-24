/*
 * Eurobot 2026 – ESP32 Drive Controller
 *
 * Core 0: stepperTask  – AccelStepper (blockierend bis fertig)
 * Core 1: uartTask     – Serial I/O, Command-Queue
 *
 * Raspi → ESP32:
 *   DD{mm}         Geradeaus  (+ vorwärts, – rückwärts)
 *   TA{deg}        Drehen     (+ im Uhrzeigersinn)
 *   ST             Sofort stoppen
 *   SP{x};{y};{t}  Odometrie setzen (kein Ack)
 *
 * ESP32 → Raspi:
 *   OK             Befehl vollständig ausgeführt
 *   INTERRUPTED    Befehl durch ST abgebrochen
 *   ERR            Unbekannter Befehl
 */

#include <Arduino.h>
#include <AccelStepper.h>

// ═══════════════════════════════════════════════════════════
//  PINS
// ═══════════════════════════════════════════════════════════
#define STEP_L  25
#define DIR_L   26
#define STEP_R  32
#define DIR_R   33

// ═══════════════════════════════════════════════════════════
//  MECHANIK
// ═══════════════════════════════════════════════════════════
#define STEPS_PER_REV    200
#define WHEEL_DIAM_MM    65.0f
#define WHEELBASE_MM    150.0f
#define DRIVE_SPEED_CM_S  10.0f
#define ACCEL_CM_S2       20.0f

static const float STEPS_PER_MM = STEPS_PER_REV / (PI * WHEEL_DIAM_MM);
static const float STEPS_PER_CM = STEPS_PER_REV / (PI * WHEEL_DIAM_MM * 0.1f);
static const float MAX_SPEED_SPS = DRIVE_SPEED_CM_S * STEPS_PER_CM;
static const float ACCEL_SPS2    = ACCEL_CM_S2     * STEPS_PER_CM;

// ═══════════════════════════════════════════════════════════
//  SHARED STATE
// ═══════════════════════════════════════════════════════════
volatile bool stopFlag = false;

// ═══════════════════════════════════════════════════════════
//  COMMAND QUEUE
// ═══════════════════════════════════════════════════════════
enum CmdType : uint8_t { CMD_DRIVE, CMD_TURN };
struct Cmd { CmdType type; float val; };
QueueHandle_t cmdQueue;

// ═══════════════════════════════════════════════════════════
//  STEPPER TASK  (Core 0)
// ═══════════════════════════════════════════════════════════
void stepperTask(void *) {
    AccelStepper motorL(AccelStepper::DRIVER, STEP_L, DIR_L);
    AccelStepper motorR(AccelStepper::DRIVER, STEP_R, DIR_R);

    motorL.setMaxSpeed(MAX_SPEED_SPS);
    motorL.setAcceleration(ACCEL_SPS2);
    motorR.setMaxSpeed(MAX_SPEED_SPS);
    motorR.setAcceleration(ACCEL_SPS2);
    motorR.setPinsInverted(true);  // Rechter Motor gespiegelt montiert: LOW = vorwärts

    Cmd cmd;
    while (true) {
        if (xQueueReceive(cmdQueue, &cmd, portMAX_DELAY) != pdTRUE) continue;
        stopFlag = false;

        long stepsL, stepsR;
        if (cmd.type == CMD_DRIVE) {
            long s = lroundf(cmd.val * STEPS_PER_MM);
            stepsL = s;
            stepsR = s;
        } else {
            // Drehung: L und R gegenläufig
            long s = lroundf(cmd.val / 360.0f * PI * WHEELBASE_MM * STEPS_PER_MM);
            stepsL =  s;
            stepsR = -s;
        }

        motorL.move(stepsL);
        motorR.move(stepsR);

        bool interrupted = false;
        while (motorL.distanceToGo() != 0 || motorR.distanceToGo() != 0) {
            if (stopFlag) {
                // Sofortiger Stopp: Ziel = aktuelle Position
                motorL.setCurrentPosition(motorL.currentPosition());
                motorR.setCurrentPosition(motorR.currentPosition());
                interrupted = true;
                break;
            }
            motorL.run();
            motorR.run();
        }

        Serial.println(interrupted ? "INTERRUPTED" : "OK");
    }
}

// ═══════════════════════════════════════════════════════════
//  UART TASK  (Core 1)
// ═══════════════════════════════════════════════════════════
static void parseCmd(const String &s) {
    Cmd cmd = {};

    if (s.startsWith("DD")) {
        cmd.type = CMD_DRIVE;
        cmd.val  = s.substring(2).toFloat();
        xQueueSend(cmdQueue, &cmd, 0);

    } else if (s.startsWith("TA")) {
        cmd.type = CMD_TURN;
        cmd.val  = s.substring(2).toFloat();
        xQueueSend(cmdQueue, &cmd, 0);

    } else if (s == "ST") {
        stopFlag = true;
        xQueueReset(cmdQueue);

    } else if (s.startsWith("SP")) {
        // Odometrie-Reset – kein Ack

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
