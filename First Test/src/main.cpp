#include <Arduino.h>
#define TRIG_1 2
#define ECHO_1 3
#define TRIG_2 4
#define ECHO_2 5

const int GEGNER_DIST = 30; // cm

long messen(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);

  long d = pulseIn(echo, HIGH, 25000);
  if (d == 0) return -1;
  return d * 0.034 / 2;
}


void setup() {
  pinMode(TRIG_1, OUTPUT);
  pinMode(ECHO_1, INPUT);
  pinMode(TRIG_2, OUTPUT);
  pinMode(ECHO_2, INPUT);

  Serial.begin(9600);
}

void loop() {
  Serial.println(messen(TRIG_1, ECHO_1));
}
