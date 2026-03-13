#include <Arduino.h>
#include <ESP32Servo.h>

// LED
#define LED_PIN 2

// Ultraschall
#define TRIG_PIN 5
#define ECHO1 18 
#define ECHO2 19
#define ECHO3 21

// Stepper 1
#define STEP1_PIN 25
#define DIR1_PIN  26

// Stepper 2
#define STEP2_PIN 32
#define DIR2_PIN  33

// Step Delay
#define STEP_DELAY_US 300
#define STEPS_TO_MOVE 10000

// Servos
#define SERVO1_PIN 22
#define SERVO2_PIN 23
Servo servo1;
Servo servo2;

// Gemeinsame Variablen
volatile bool enemyDetected = false;
volatile unsigned long stopUntil = 0;
volatile long stepCounter = 0;

long readDistance(int echoPin)
{
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    long duration = pulseIn(echoPin, HIGH, 30000);
    if(duration == 0) return -1;

    long distance = duration * 0.034 / 2;
    return distance;
}

// --- Konfiguration (anpassen!) ---
#define STEPS_PER_REV     200      // Schritte pro Umdrehung deines Steppers
#define WHEEL_DIAMETER_CM 6.5f     // Raddurchmesser in cm
#define WHEELBASE_CM      15.0f    // Abstand zwischen den Rädern in cm

static int servoPos = 0; // aktuell gespeicherte Servo-Position

// --- Interne Hilfsfunktion ---
// dir1/dir2: true = HIGH, false = LOW
void stepBoth(bool dir1, bool dir2, long steps) {
    digitalWrite(DIR1_PIN, dir1 ? HIGH : LOW);
    digitalWrite(DIR2_PIN, dir2 ? HIGH : LOW);

    for (long i = 0; i < steps; i++) {
        // Hindernis-Check
        portENTER_CRITICAL(&mux);
        bool blocked = millis() < stopUntil;
        portEXIT_CRITICAL(&mux);

        while (blocked) {
            delay(1);
            portENTER_CRITICAL(&mux);
            blocked = millis() < stopUntil;
            portEXIT_CRITICAL(&mux);
        }

        digitalWrite(STEP1_PIN, HIGH);
        digitalWrite(STEP2_PIN, HIGH);
        delayMicroseconds(STEP_DELAY_US);
        digitalWrite(STEP1_PIN, LOW);
        digitalWrite(STEP2_PIN, LOW);
        delayMicroseconds(STEP_DELAY_US);
    }
}

// --- Öffentliche Methoden ---

// Positiv = vorwärts, negativ = rückwärts
void drive(float cm) {
    long steps = (long)(fabsf(cm) * STEPS_PER_REV / (PI * WHEEL_DIAMETER_CM));
    bool fwd = cm >= 0;
    stepBoth(fwd, !fwd, steps); // Motor 2 ist gespiegelt montiert
}

// Positiv = Uhrzeigersinn, negativ = gegen Uhrzeigersinn
void turnAngle(float angle) {
    float arcCm = fabsf(angle) / 360.0f * PI * WHEELBASE_CM;
    long steps = (long)(arcCm * STEPS_PER_REV / (PI * WHEEL_DIAMETER_CM));
    bool cw = angle >= 0;
    stepBoth(cw, cw, steps); // beide Motoren gleiche Richtung = Drehung
}

void servoUp() {
    for (; servoPos <= 180; servoPos++) {
        servo1.write(servoPos);
        servo2.write(servoPos);
        delay(10);
    }
}

void servoDown() {
    for (; servoPos >= 0; servoPos--) {
        servo1.write(servoPos);
        servo2.write(servoPos);
        delay(10);
    }
}

// Sensor + LED Task (Core 0)
void ledTask(void *pvParameters)
{
    pinMode(LED_PIN, OUTPUT);
    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO1, INPUT);
    pinMode(ECHO2, INPUT);
    pinMode(ECHO3, INPUT);

    while (true)
    {
        long d1 = readDistance(ECHO1);
        long d2 = readDistance(ECHO2);
        long d3 = readDistance(ECHO3);

        bool detected = false;
        if(d1 != -1 && d1 < 30) detected = true;
        if(d2 != -1 && d2 < 30) detected = true;
        if(d3 != -1 && d3 < 30) detected = true;

        if(detected) stopUntil = millis() + 2000; // 2 Sekunden stoppen
        enemyDetected = detected;

        digitalWrite(LED_PIN, detected);

        vTaskDelay(50 / portTICK_PERIOD_MS);
    }
}

portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;

void loopingStepper(void *pvParameters)
{
    pinMode(STEP1_PIN, OUTPUT);
    pinMode(DIR1_PIN, OUTPUT);
    pinMode(STEP2_PIN, OUTPUT);
    pinMode(DIR2_PIN, OUTPUT);

    digitalWrite(DIR1_PIN, HIGH);
    digitalWrite(DIR2_PIN, LOW);

    drive(50);        // 50 cm vorwärts
    turnAngle(90);    // 90° rechts
    servoUp();
    drive(20);
    servoDown();
    vTaskDelete(NULL);
}

void setup()
{
    // Servos initialisieren
    servo1.attach(SERVO1_PIN);
    servo2.attach(SERVO2_PIN);

    // Sensor/LED Task auf Core 0
    xTaskCreatePinnedToCore(ledTask, "LedTask", 4096, NULL, 1, NULL, 0);

    // Stepper Task auf Core 1
    xTaskCreatePinnedToCore(loopingStepper, "StepperLoop", 4096, NULL, 1, NULL, 1);

    // Warten bis Stepper-Task abgeschlossen
    while (stepCounter < STEPS_TO_MOVE)
    {
        delay(10);
    }

    // Servos 0 -> 180 -> 0 bewegen
    for (int pos = 0; pos <= 180; pos++)
    {
        servo1.write(pos);
        servo2.write(pos);
        delay(10);
    }
    for (int pos = 180; pos >= 0; pos--)
    {
        servo1.write(pos);
        servo2.write(pos);
        delay(10);
    }
}

void loop() {}