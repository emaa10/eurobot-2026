// ============================================================
// IHSS57 – Dual Motor ESP32 WROOM-32
// Dauerlauf (Links / Rechts)
// ============================================================

#include <Arduino.h>

// ── Pins ────────────────────────────────────────────────
#define STEP_R        26
#define DIR_R         27
#define STEP_L        33
#define DIR_L         25
#define ENDSTOP_PIN    5

// ── Setup ───────────────────────────────────────────────
#define STEPS_PER_REV  1600
#define DEFAULT_RPM     60.0f

// ── Delay Funktion (ESP32 sicher) ───────────────────────
static inline void delayUs(uint32_t us) {
  ets_delay_us(us);
}

// ── Endstop ──────────────────────────────────────────────
bool endstopTriggered() {
  return digitalRead(ENDSTOP_PIN) == LOW;
}

// ── RPM → Delay ──────────────────────────────────────────
uint32_t rpmToDelay(float rpm) {
  float us = (60.0f * 1000000.0f) / (rpm * STEPS_PER_REV) / 2.0f;
  if (us < 2.0f) us = 2.0f;
  return (uint32_t)us;
}

// ── Puls ────────────────────────────────────────────────
void pulse(uint8_t mask, uint32_t halfDelay) {
  if (mask & 0x01) digitalWrite(STEP_R, HIGH);
  if (mask & 0x02) digitalWrite(STEP_L, HIGH);

  delayUs(halfDelay);

  if (mask & 0x01) digitalWrite(STEP_R, LOW);
  if (mask & 0x02) digitalWrite(STEP_L, LOW);

  delayUs(halfDelay);
}

// ── Setup Richtung ──────────────────────────────────────
void setDir(bool right, bool left, bool cw) {
  if (right) digitalWrite(DIR_R, cw);
  if (left)  digitalWrite(DIR_L, cw);

  delayUs(5); // DIR setup time
}

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);

  pinMode(STEP_R, OUTPUT);
  pinMode(DIR_R, OUTPUT);
  pinMode(STEP_L, OUTPUT);
  pinMode(DIR_L, OUTPUT);
  pinMode(ENDSTOP_PIN, INPUT_PULLUP);

  digitalWrite(STEP_R, LOW);
  digitalWrite(STEP_L, LOW);
  digitalWrite(DIR_R, LOW);
  digitalWrite(DIR_L, LOW);

  Serial.println("System ready");
}

// ============================================================
// LOOP → ENDLOS DREHEN
// ============================================================
void loop() {
  static uint32_t d = rpmToDelay(DEFAULT_RPM);

  // Richtung fest (beide Motoren CW)
  setDir(true, true, true);

  // Dauerlauf
  pulse(0x03, d);
}