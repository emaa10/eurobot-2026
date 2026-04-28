#include "robot.h"
#include "servo.h"
#include <Arduino.h>

void runTactic() {
    servoInit();

    // 1 m vorwärts mit Gegnererkennung (pausiert automatisch bei Hindernis)
    driveMM(1000);

    // Servo dreht unbegrenzt
    servoSpinForever();
}
