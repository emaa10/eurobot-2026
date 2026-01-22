#include <Arduino.h>
#include <NewPing.h>
//#include <AccelStepper.h>
#define TRIG_1 2
#define ECHO_1 3
#define TRIG_2 4
#define ECHO_2 5
#define TRIG_3 6
#define ECHO_3 7
#define TRIG_4 8
#define ECHO_4 9

//#define ARLAMMMMMMM 1
#define L_STEP 10
#define L_DIR 11
#define R_STEP 12
#define R_DIR 13


/*AccelStepper stepperLeft(AccelStepper::DRIVER, L_STEP, L_DIR);
AccelStepper stepperRight(AccelStepper::DRIVER, R_STEP, R_DIR);*/

const int GEGNER_DIST = 15; // cm
bool ALARM = false;
#define MAX_DIST 50   // cm
unsigned long lastPing = 0;
const unsigned long pingInterval = 50; // ms
const unsigned int tperStep = 600;

NewPing sonar1(TRIG_1, ECHO_1, MAX_DIST);
NewPing sonar2(TRIG_2, ECHO_2, MAX_DIST);
NewPing sonar3(TRIG_3, ECHO_3, MAX_DIST);
NewPing sonar4(TRIG_4, ECHO_4, MAX_DIST);

int messen(NewPing &sonar) {
  int d = sonar.ping_cm();
  if (d == 0) return -1;
  return d;
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
  pinMode(L_STEP, OUTPUT);
  pinMode(L_DIR, OUTPUT);
  pinMode(R_STEP, OUTPUT);    
  //pinMode(ARLAMMMMMMM, OUTPUT);
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
}

void gegi() {
    int d1 = sonar1.ping_cm();
    int d2 = sonar2.ping_cm();
    int d3 = sonar3.ping_cm();

    // Alarm Logik
    ALARM = false;
    if ((d1 != 0 && d1 <= GEGNER_DIST) || 
        (d2 != 0 && d2 <= GEGNER_DIST) || 
        (d3 != 0 && d3 <= GEGNER_DIST)) 
    {
      ALARM = true;
      digitalWrite(LED_BUILTIN, HIGH);
      while ((d1 != 0 && d1 <= GEGNER_DIST) || 
        (d2 != 0 && d2 <= GEGNER_DIST) || 
        (d3 != 0 && d3 <= GEGNER_DIST))
      {
        delay(10);
        d1 = sonar1.ping_cm();
        d2 = sonar2.ping_cm();
        d3 = sonar3.ping_cm();
      } 
    }
    else {
      ALARM = false;
      digitalWrite(LED_BUILTIN, LOW);
    }
}

void drive(int steps, bool dir, bool gegnerCheck) {
  unsigned long tStart = micros();
  for (int i = 0; i < steps; i++)
  {
    tStart = micros();
    digitalWrite(L_STEP, HIGH);
    digitalWrite(R_STEP, HIGH);
    if (gegnerCheck){
      gegi();
      while (micros() - tStart < tperStep) {}
    }
    else {
      delayMicroseconds(tperStep);
    }
    tStart = micros();
    digitalWrite(L_STEP, LOW);
    digitalWrite(R_STEP, LOW);
    if (gegnerCheck){
        gegi();
        while (micros() - tStart < tperStep) {}
      }
      else {
        delayMicroseconds(tperStep);
      }
  }
}




void loop() {
  /*// Stepper laufen lassen

  // Ultraschall nur alle pingInterval ms
  if(millis() - lastPing >= pingInterval) {
    lastPing = millis();

    // Non-blocking messen
    int d1 = sonar1.ping_cm();
    int d2 = sonar2.ping_cm();
    int d3 = sonar3.ping_cm();

    // Alarm Logik
    ALARM = false;
    if ((d1 != 0 && d1 <= GEGNER_DIST) || 
        (d2 != 0 && d2 <= GEGNER_DIST) || 
        (d3 != 0 && d3 <= GEGNER_DIST)) 
    {
      ALARM = true;
    }

    // LED setzen
    digitalWrite(LED_BUILTIN, ALARM ? HIGH : LOW);*/
    drive(200,true,false); // Vorwaerts 200 Schritte
  
}

