#include <Arduino.h>
#define STEP1 25
#define DIR1  26

#define STEP2 32
#define DIR2  33

void setup() {
  pinMode(STEP1, OUTPUT);
  pinMode(DIR1, OUTPUT);
  pinMode(STEP2, OUTPUT);
  pinMode(DIR2, OUTPUT);

  digitalWrite(DIR1, HIGH);
  digitalWrite(DIR2, HIGH);
}

void loop() {

  digitalWrite(STEP1, HIGH);
  digitalWrite(STEP2, HIGH);
  delayMicroseconds(500);

  digitalWrite(STEP1, LOW);
  digitalWrite(STEP2, LOW);
  delayMicroseconds(500);

}