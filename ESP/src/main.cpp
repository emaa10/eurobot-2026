#include <Arduino.h>

// ── Pins ─────────────────────────────
#define STEP_R  26
#define DIR_R   27
#define STEP_L  33
#define DIR_L   25
#define EN_L    32
#define EN_R    35
const int led = 2;

// ── Speed ────────────────────────────
int delayTime = 200; // kleiner = schneller

void setup() {
  pinMode(STEP_R, OUTPUT);
  pinMode(DIR_R,  OUTPUT);
  pinMode(STEP_L, OUTPUT);
  pinMode(DIR_L,  OUTPUT);
  pinMode(EN_L,   OUTPUT);
  pinMode(EN_R,   OUTPUT);

  // Treiber aktivieren (LOW = aktiv bei den meisten Stepper-Treibern)
  digitalWrite(EN_L, LOW);
  digitalWrite(EN_R, LOW);

  // Richtung fest
  digitalWrite(DIR_R, HIGH);
  digitalWrite(DIR_L, HIGH);
  pinMode(led, OUTPUT);
  digitalWrite(led, HIGH);
}

void loop() {
  // beide Motoren einen Schritt
  digitalWrite(STEP_R, HIGH);
  digitalWrite(STEP_L, HIGH);
  delayMicroseconds(delayTime);
  digitalWrite(STEP_R, LOW);
  digitalWrite(STEP_L, LOW);
  delayMicroseconds(delayTime);
}