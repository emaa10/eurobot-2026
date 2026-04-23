#ifndef MOTOR_H
#define MOTOR_H

#include <stdint.h>
#include <stdbool.h>

void motorInit(void);
void step_pulse(uint pin);
void setDistancemm(int d1, int d2);
void driveForward();
void blockMotors();
void turn(bool direction);

#endif
