#include "Arduino.h"

void setup() {
    Serial.begin(115200);
    Serial.println("Hello SIMA-Neu!");
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, HIGH);
}

void loop() {
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    delay(500);
}