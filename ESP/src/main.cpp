#include <Arduino.h>

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

// gemeinsame Variable zwischen den Cores
volatile bool enemyDetected = false;


long readDistance(int echoPin)
{
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);

    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    long duration = pulseIn(echoPin, HIGH, 30000);

    if(duration == 0)
        return -1;

    long distance = duration * 0.034 / 2;
    return distance;
}


// Sensor Task (Core 0)
void ledTask(void *pvParameters) {

    pinMode(LED_PIN, OUTPUT);

    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO1, INPUT);
    pinMode(ECHO2, INPUT);
    pinMode(ECHO3, INPUT);

    while (true) {

        long d1 = readDistance(ECHO1);
        long d2 = readDistance(ECHO2);
        long d3 = readDistance(ECHO3);

        bool detected = false;

        if(d1 != -1 && d1 < 30) detected = true;
        if(d2 != -1 && d2 < 30) detected = true;
        if(d3 != -1 && d3 < 30) detected = true;

        enemyDetected = detected;

        digitalWrite(LED_PIN, detected);

        vTaskDelay(50 / portTICK_PERIOD_MS);
    }
}


// Stepper Loop (Core 1)
void loopingStepper(void *pvParameters) {

    pinMode(STEP1_PIN, OUTPUT);
    pinMode(DIR1_PIN, OUTPUT);

    pinMode(STEP2_PIN, OUTPUT);
    pinMode(DIR2_PIN, OUTPUT);

    digitalWrite(DIR1_PIN, HIGH);
    digitalWrite(DIR2_PIN, LOW);

    while (true) {

        // Motor stoppen wenn Gegner erkannt
        if(enemyDetected)
        {
            delayMicroseconds(100);
            continue;
        }

        digitalWrite(STEP1_PIN, HIGH);
        digitalWrite(STEP2_PIN, HIGH);

        delayMicroseconds(STEP_DELAY_US);

        digitalWrite(STEP1_PIN, LOW);
        digitalWrite(STEP2_PIN, LOW);

        delayMicroseconds(STEP_DELAY_US);
    }
}


void setup() {

    xTaskCreatePinnedToCore(
        ledTask,
        "LedTask",
        4096,
        NULL,
        1,
        NULL,
        0
    );

    xTaskCreatePinnedToCore(
        loopingStepper,
        "StepperLoop",
        4096,
        NULL,
        1,
        NULL,
        1
    );
}

void loop() {
}