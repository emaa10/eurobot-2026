#include <Arduino.h>

#define LED_PIN 2

void setup() {
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_PIN, HIGH); // LED an
  delay(500);

  digitalWrite(LED_PIN, LOW);  // LED aus
  delay(500);
}