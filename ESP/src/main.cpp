#include <Arduino.h>

// ═══════════════════════════════════════════════════════════
//  PINS  – nur Stepper
// ════════════════════════════════════════════════
#define STEP_R  26 //fixed
#define DIR_R   27
#define DIR_L   25
#define STEP_L  33
#define LED_BUILTIN 2

//fuck u claude

void setup() {
  Serial.begin(115200);
  pinMode(STEP_R, OUTPUT);
  pinMode(DIR_R, OUTPUT);
  pinMode(STEP_L, OUTPUT);
  pinMode(DIR_L, OUTPUT);
  /*pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(DIR_R, LOW);
  digitalWrite(DIR_L, LOW);
  digitalWrite(STEP_L, LOW);
  digitalWrite(STEP_R, HIGH);*/
}

void loop() {
  //drive forward
  digitalWrite(DIR_R, HIGH);
  digitalWrite(DIR_L, LOW);
  digitalWrite(LED_BUILTIN, HIGH); // turn on LED to indicate movement
  for (int i = 0; i < 50000; i++) {
    digitalWrite(STEP_R, HIGH);
    digitalWrite(STEP_L, HIGH);
    delayMicroseconds(500); // adjust speed by changing delay
    digitalWrite(STEP_R, LOW);
    digitalWrite(STEP_L, LOW);
    delayMicroseconds(500); // adjust speed by changing delay
  }
  Serial.println("Moved forward");
  delay(1000); // wait before next movement
}