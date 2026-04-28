#include "servo.h"
#include <Arduino.h>
#include <Servo.h>

#define SERVO_PIN 22

static Servo servo;

void servoInit() {
    servo.attach(SERVO_PIN);
    servo.writeMicroseconds(1500);  // neutral / stop
}

void servoSpinForever() {
    servo.writeMicroseconds(2000);  // full speed
    while (true) delay(1000);
}
