#include <Arduino.h>
#include "hardware/timer.h"

extern "C" {
    #include "tof.h"
    #include "motor.h"
    #include "servo.h"
    #include "pullcord.h"
    #include "teamswitch.h"
}

int SIMA_number = 2;
bool programm_ende = false;
int spielzeit = 0;
volatile bool timer_aufruf = false;

struct repeating_timer timer_inst;

bool general_timer(struct repeating_timer *t) {
    timer_aufruf = true;
    return true;
}

void setup() {
    vl53Init();
    motorInit();
    servoInit();
    pullcordInit();
    teamswitchInit();
    add_repeating_timer_ms(-1, general_timer, NULL, &timer_inst);
}

void loop() {
    if (timer_aufruf) {
        timer_aufruf = false;
        teamswitchRead();
        pullcordRead();
        spielzeit++;

        uint16_t d1 = vl53_read_distance(i2c1);
        uint16_t d2 = vl53_read_distance(i2c0);
        if (spielzeit >= 85000) {
            setDistancemm((int)d1, (int)d2);  // fix: war getDistancemm()
            driveForward();                    // fix: war drive() (existiert nicht)
        }
        if (spielzeit >= 100000) {
            blockMotors();
            servoTurn();
        }
    }
}
