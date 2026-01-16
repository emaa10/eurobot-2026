#include <Arduino.h>
#define TRIG_1 2
#define ECHO_1 3
#define TRIG_2 4
#define ECHO_2 5
#define TRIG_3 6
#define ECHO_3 7
#define TRIG_4 8
#define ECHO_4 9
#define TRIG_5 10
#define ECHO_5 11
#define TRIG_6 12
#define ECHO_6 13
#define ARLAMMMMMMM 1

const int GEGNER_DIST = 15; // cm
bool ALARM = false;

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
  pinMode(TRIG_3, OUTPUT);
  pinMode(ECHO_3, INPUT);
  pinMode(ARLAMMMMMMM, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  if (messen(TRIG_1,ECHO_1) <= GEGNER_DIST || messen(TRIG_2,ECHO_2) <= GEGNER_DIST || messen(TRIG_3,ECHO_3))
  {
    ALARM = true;
    digitalWrite(ARLAMMMMMMM, HIGH); //to communicate with other controller
    digitalWrite(LED_BUILTIN, HIGH);
  }
  else{
    ALARM = false;
    digitalWrite(ARLAMMMMMMM, LOW);
    digitalWrite(LED_BUILTIN, LOW);
  }
 delay(10);
}
