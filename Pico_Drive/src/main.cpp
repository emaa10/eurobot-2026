#include <Arduino.h>
#include <AccelStepper.h>
//#include "com.h"

#define L_STEP 1
#define L_DIR 2
#define R_STEP 3
#define R_DIR 4
#define STOP_PIN 5

AccelStepper stepperLeft(AccelStepper::DRIVER, L_STEP, L_DIR);
AccelStepper stepperRight(AccelStepper::DRIVER, R_STEP, R_DIR);

//Interrupt Flag
volatile bool emergencyStop = false;

void stopISR() {
  emergencyStop = true;
}

void setSpeed(float left, float right) {
  stepperLeft.setSpeed(left);
  stepperRight.setSpeed(right);
}


void geradeaus(float speed) {
  setSpeed(speed, speed);
}


void drehen(float speed) {
  setSpeed(speed, -speed);
}

void stopMotoren() {
  stepperLeft.setSpeed(0);
  stepperRight.setSpeed(0);
}

void setup() {
  pinMode(STOP_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(STOP_PIN), stopISR, FALLING);

  stepperLeft.setMaxSpeed(2000);
  stepperRight.setMaxSpeed(2000);

  stepperLeft.setAcceleration(1000);
  stepperRight.setAcceleration(1000);
}

void loop() {
  if (emergencyStop) {
    stopMotoren();
    return;
  }
  stepperLeft.runSpeed();
  stepperRight.runSpeed();
}
