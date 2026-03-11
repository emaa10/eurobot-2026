#include <Arduino.h>

// LED
#define LED_PIN 2

// Stepper 1
#define STEP1_PIN 25
#define DIR1_PIN  26

// Stepper 2
#define STEP2_PIN 32
#define DIR2_PIN  33

// Step Delay (Geschwindigkeit)
#define STEP_DELAY_US 500

// LED Task (Core 0)
void ledTask(void *pvParameters) {

    pinMode(LED_PIN, OUTPUT);

    while (true) {

        digitalWrite(LED_PIN, HIGH);
        vTaskDelay(500 / portTICK_PERIOD_MS);

        digitalWrite(LED_PIN, LOW);
        vTaskDelay(500 / portTICK_PERIOD_MS);
    }
}

// Stepper Loop (Core 1)
void loopingStepper(void *pvParameters) {

    pinMode(STEP1_PIN, OUTPUT);
    pinMode(DIR1_PIN, OUTPUT);

    pinMode(STEP2_PIN, OUTPUT);
    pinMode(DIR2_PIN, OUTPUT);

    // Richtung setzen
    digitalWrite(DIR1_PIN, HIGH);
    digitalWrite(DIR2_PIN, LOW);

    while (true) {

        // STEP HIGH
        digitalWrite(STEP1_PIN, HIGH);
        digitalWrite(STEP2_PIN, HIGH);

        delayMicroseconds(STEP_DELAY_US);

        // STEP LOW
        digitalWrite(STEP1_PIN, LOW);
        digitalWrite(STEP2_PIN, LOW);

        delayMicroseconds(STEP_DELAY_US);
    }
}

void setup() {

    // LED Task auf Core 0
    xTaskCreatePinnedToCore(
        ledTask,
        "LedTask",
        1024,
        NULL,
        1,
        NULL,
        0
    );

    // Stepper Loop auf Core 1
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
    // leer
}