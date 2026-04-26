#include <Arduino.h>

void setup() {
    Serial.begin(115200);
    pinMode(LED_BUILTIN, OUTPUT);
    Serial.println("Blink-Test gestartet");
}

void loop() {
    digitalWrite(LED_BUILTIN, HIGH);
    Serial.println("LED an");
    delay(500);

    digitalWrite(LED_BUILTIN, LOW);
    Serial.println("LED aus");
    delay(500);
}
