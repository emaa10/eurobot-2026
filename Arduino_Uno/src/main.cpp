#include <Arduino.h>
#include <NewPing.h>
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
#define MAX_DIST 200   // cm

NewPing sonar1(TRIG_1, ECHO_1, MAX_DIST);
NewPing sonar2(TRIG_2, ECHO_2, MAX_DIST);
NewPing sonar3(TRIG_3, ECHO_3, MAX_DIST);
NewPing sonar4(TRIG_4, ECHO_4, MAX_DIST);
NewPing sonar5(TRIG_5, ECHO_5, MAX_DIST);
NewPing sonar6(TRIG_6, ECHO_6, MAX_DIST);

int messen(NewPing &sonar) {
  delay(50);                  // Mindestpause
  int dist = sonar.ping_cm(); // Ergebnis in cm

  if (dist == 0) return -1;   // kein Echo / außerhalb MAX_DIST
  return dist;
}

void setup() {
  pinMode(TRIG_1, OUTPUT);
  pinMode(ECHO_1, INPUT);
  pinMode(TRIG_2, OUTPUT);
  pinMode(ECHO_2, INPUT);
  pinMode(TRIG_3, OUTPUT);
  pinMode(ECHO_3, INPUT);
  pinMode(TRIG_4, OUTPUT);
  pinMode(ECHO_4, INPUT);
  pinMode(TRIG_5, OUTPUT);
  pinMode(ECHO_5, INPUT);
  pinMode(TRIG_6, OUTPUT);
  pinMode(ECHO_6, INPUT);
  pinMode(ARLAMMMMMMM, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(9600);
}

void testUs() {
  int distance = messen((sonar3));
  Serial.println(distance);
  if(distance <= GEGNER_DIST) {
    digitalWrite(LED_BUILTIN, HIGH);
  }
  else {
    digitalWrite(LED_BUILTIN, LOW);
  }
  delay(10);
}


void loop() {
  int d1 = messen(sonar1);
  int d2 = messen(sonar2);
  int d3 = messen(sonar3);
  if ((d1 <= GEGNER_DIST && d1 != -1) || (d2 <= GEGNER_DIST && d2 != -1) || (d3 <= GEGNER_DIST && d3 != -1))
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
}

