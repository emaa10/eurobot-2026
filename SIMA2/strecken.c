#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/pwm.h"

#include "motor.h"
#include "strecken.h"

void StreckeSIMA2()
{
    driveForward();
    turn(1);
    driveForward();
    blockMotors();
}

