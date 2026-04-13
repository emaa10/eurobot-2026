#include <Arduino.h>

// --- Pins ---
#define STEP_L  25
#define DIR_L   26
#define STEP_R  32
#define DIR_R   33

// --- Geometrie ---
#define STEPS_PER_REV   200
#define WHEEL_DIAM_CM   6.5f
#define WHEELBASE_CM    15.0f
static const float STEPS_PER_CM = STEPS_PER_REV / (PI * WHEEL_DIAM_CM);

// --- Shared State ---
portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
volatile bool  stopFlag = false;
volatile long  posL = 0, posR = 0;   // steps (vorwärts positiv)
volatile float spdL = 10.0f;          // cm/s
volatile float spdR = 10.0f;

// --- Command Queue ---
enum CmdType { CMD_DRIVE, CMD_TURN, CMD_SPEED };
struct Cmd { CmdType type; float p1, p2; };
QueueHandle_t cmdQueue;

// cm/s → halbe Periodendauer in µs
static int toDelayUs(float cmS) {
    if (cmS <= 0.0f) return 5000;
    int d = (int)(500000.0f / (cmS * STEPS_PER_CM));
    return max(d, 100);
}

// Beide Motoren gleichzeitig schrittweise fahren, jeder mit eigener Geschwindigkeit.
// dirL/dirR: HIGH oder LOW (Hardwarepegel, Motor R ist gespiegelt montiert)
// Rückgabe: false wenn durch STOP unterbrochen
bool doSteps(uint8_t dirL, uint8_t dirR, long stepsL, long stepsR) {
    digitalWrite(DIR_L, dirL);
    digitalWrite(DIR_R, dirR);

    int dL = toDelayUs(spdL), dR = toDelayUs(spdR);
    long doneL = 0, doneR = 0;
    unsigned long nextL = micros(), nextR = micros();

    while (doneL < stepsL || doneR < stepsR) {
        if (stopFlag) return false;
        unsigned long now = micros();

        if (doneL < stepsL && (long)(now - nextL) >= 0) {
            digitalWrite(STEP_L, HIGH);
            delayMicroseconds(5);
            digitalWrite(STEP_L, LOW);
            nextL = now + (unsigned long)(dL * 2);
            portENTER_CRITICAL(&mux);
            posL += (dirL == HIGH) ? 1 : -1;
            portEXIT_CRITICAL(&mux);
            doneL++;
        }
        if (doneR < stepsR && (long)(now - nextR) >= 0) {
            digitalWrite(STEP_R, HIGH);
            delayMicroseconds(5);
            digitalWrite(STEP_R, LOW);
            nextR = now + (unsigned long)(dR * 2);
            // R ist gespiegelt: LOW = vorwärts → posR += 1
            portENTER_CRITICAL(&mux);
            posR += (dirR == LOW) ? 1 : -1;
            portEXIT_CRITICAL(&mux);
            doneR++;
        }
    }
    return true;
}

// --- Core 0: Stepper-Task ---
void stepperTask(void *) {
    pinMode(STEP_L, OUTPUT); pinMode(DIR_L, OUTPUT);
    pinMode(STEP_R, OUTPUT); pinMode(DIR_R, OUTPUT);

    Cmd cmd;
    while (true) {
        if (xQueueReceive(cmdQueue, &cmd, portMAX_DELAY) != pdTRUE) continue;
        stopFlag = false;

        if (cmd.type == CMD_SPEED) {
            spdL = cmd.p1;
            spdR = cmd.p2;
            Serial.println("OK");
            continue;
        }

        bool ok;
        if (cmd.type == CMD_DRIVE) {
            long steps = (long)(fabsf(cmd.p1) * STEPS_PER_CM);
            bool fwd = cmd.p1 >= 0;
            // vorwärts: L=HIGH, R=LOW (gespiegelt)
            ok = doSteps(fwd ? HIGH : LOW, fwd ? LOW : HIGH, steps, steps);
        } else { // CMD_TURN
            float arc = fabsf(cmd.p1) / 360.0f * PI * WHEELBASE_CM;
            long steps = (long)(arc * STEPS_PER_CM);
            bool cw = cmd.p1 >= 0;
            // CW: L vorwärts, R vorwärts (gespiegelt → beide HIGH drehen auf der Stelle)
            ok = doSteps(cw ? HIGH : LOW, cw ? HIGH : LOW, steps, steps);
        }
        Serial.println(ok ? "OK" : "INTERRUPTED");
    }
}

// --- Core 1: UART-Task ---
static void parseCmd(const String &s) {
    Cmd cmd = {};
    if (s.startsWith("DRIVE ")) {
        cmd.type = CMD_DRIVE;
        cmd.p1   = s.substring(6).toFloat();
        xQueueSend(cmdQueue, &cmd, 0);

    } else if (s.startsWith("TURN ")) {
        cmd.type = CMD_TURN;
        cmd.p1   = s.substring(5).toFloat();
        xQueueSend(cmdQueue, &cmd, 0);

    } else if (s.startsWith("SPEED ")) {
        // "SPEED <links_cm_s> <rechts_cm_s>"
        String rest = s.substring(6);
        int sp = rest.indexOf(' ');
        cmd.type = CMD_SPEED;
        cmd.p1   = (sp < 0) ? rest.toFloat() : rest.substring(0, sp).toFloat();
        cmd.p2   = (sp < 0) ? cmd.p1         : rest.substring(sp + 1).toFloat();
        xQueueSend(cmdQueue, &cmd, 0);

    } else if (s == "STOP") {
        stopFlag = true;
        xQueueReset(cmdQueue);
        Serial.println("OK");

    } else if (s == "POS") {
        long l, r;
        portENTER_CRITICAL(&mux); l = posL; r = posR; portEXIT_CRITICAL(&mux);
        Serial.printf("POS %.2f %.2f\n", l / STEPS_PER_CM, r / STEPS_PER_CM);

    } else {
        Serial.println("ERR unknown command");
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

void setup() {
    Serial.begin(115200);
    cmdQueue = xQueueCreate(16, sizeof(Cmd));
    xTaskCreatePinnedToCore(stepperTask, "Stepper", 4096, NULL, 2, NULL, 0);
    xTaskCreatePinnedToCore(uartTask,    "UART",    4096, NULL, 1, NULL, 1);
}

void loop() {
    vTaskDelay(1000 / portTICK_PERIOD_MS);
}
