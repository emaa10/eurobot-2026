#include <Arduino.h>
// ── Pins ─────────────────────────────
#define STEP_R 2
#define DIR_R  3
#define STEP_L 4
#define DIR_L  5

// ── Speed ────────────────────────────
int delayTime = 500; // kleiner = schneller

void setup() {
  pinMode(STEP_R, OUTPUT);
  pinMode(DIR_R, OUTPUT);
  pinMode(STEP_L, OUTPUT);
  pinMode(DIR_L, OUTPUT);

  // Richtung fest
  digitalWrite(DIR_R, HIGH);
  digitalWrite(DIR_L, HIGH);
}

void loop() {
  // beide Motoren Schritt
  digitalWrite(STEP_R, HIGH);
  digitalWrite(STEP_L, HIGH);
  delayMicroseconds(delayTime);

  digitalWrite(STEP_R, LOW);
  digitalWrite(STEP_L, LOW);
  delayMicroseconds(delayTime);
}