#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/pwm.h"
#include "hardware/timer.h"
#include "motor.h"

volatile uint16_t steps_target_drive = 980;
volatile uint16_t steps_target_turn = 200;

bool hard_stop_active = false;

int distanz1 = 2000;
int distanz2 = 2000;

// Motorsteuerung
float delay_left  = 6000.0f;
float delay_right = 6000.0f;
const float target_delay = 2500.0f;
const float ramp_step = 200.0f;

float acc_left = 0.0f;
float acc_right = 0.0f;

typedef enum {
    PHASE_DRIVE_1M,
    PHASE_TURN_90,
    PHASE_NORMAL
} drive_phase_t;

volatile drive_phase_t phase = PHASE_DRIVE_1M;

// Step-Zähler
volatile uint32_t step_counter = 0;

// Radumfang 65mm → 1m ≈ 980 Steps
const uint32_t STEPS_FOR_1M = 980;

// 90° Drehung ≈ 245 Steps
const uint32_t STEPS_FOR_90DEG = 200;


void motorInit(void)
{
    #define L_STEP 0
    #define L_DIR  1
    #define L_EN   7

    #define R_STEP 10
    #define R_DIR  9
    #define R_EN   15

    gpio_init(L_STEP); gpio_set_dir(L_STEP, GPIO_OUT);
    gpio_init(L_DIR);  gpio_set_dir(L_DIR, GPIO_OUT);
    gpio_init(L_EN);   gpio_set_dir(L_EN, GPIO_OUT);

    gpio_init(R_STEP); gpio_set_dir(R_STEP, GPIO_OUT);
    gpio_init(R_DIR);  gpio_set_dir(R_DIR, GPIO_OUT);
    gpio_init(R_EN);   gpio_set_dir(R_EN, GPIO_OUT);

    gpio_put(L_DIR, 1);
    gpio_put(R_DIR, 0);

    gpio_put(L_EN, 1);
    gpio_put(R_EN, 1);
}

// Step Pulse erzeugen
void step_pulse(uint pin) {
    gpio_put(pin, 1);
    sleep_us(30);
    gpio_put(pin, 0);

    // Step-Zähler nur in Phase 1 und 2
    if (phase == PHASE_DRIVE_1M || phase == PHASE_TURN_90) {
        step_counter++;
    }
}

void setDistancemm(int d1, int d2)
{
    distanz1 = d1;
    distanz2 = d2;
}

void driveForward()
{
    // STEP PULSE AM ANFANG!!!!!!

    // ToF-Sicherheitslogik 
    static int below_counter1 = 0;

    // Hard-Stop < 50 cm
    if (distanz1 < 500 ||distanz2 < 500) {
        below_counter1++;
    } else {
        below_counter1 = 0;
    }

    if (below_counter1 >= 150) {
        // Sofort stoppen 
        gpio_put(L_EN, 1);
        gpio_put(R_EN, 1);
        hard_stop_active = true;
        acc_left = acc_right = 0;
    }

    // Wiederanfahren erst bei > 54 cm
    if (hard_stop_active && distanz1 > 540 && distanz2 >540 ) {
        gpio_put(L_EN, 0);
        gpio_put(R_EN, 0);

        delay_left  = 6000.0f;
        delay_right = 6000.0f;
        acc_left = acc_right = 0;

        hard_stop_active = false;
    }

}

void blockMotors()
{
    gpio_put(L_EN, 0);
    gpio_put(R_EN, 0);
}

void turn(bool direction)   //90° Drehung links oder rechtsrum
{
    if(direction == 1)
    {
        // Sanfte Deceleration nur bei 1m-Steeckenstopp
        const uint32_t DECEL_START = STEPS_FOR_1M - 100;  // 100 Steps vorher abbremsen

        if (step_counter >= DECEL_START) {
            delay_left  += 150.0f;
            delay_right += 150.0f;

            if (delay_left > 12000.0f)  delay_left  = 12000.0f;
            if (delay_right > 12000.0f) delay_right = 12000.0f;
        }

        // Motoren sauber stoppen
        gpio_put(L_EN, 1);
        gpio_put(R_EN, 1);

        acc_left = acc_right = 0;

        step_counter = 0;

        // Drehrichtung setzen (links vorwärts, rechts rückwärts)
        gpio_put(L_DIR, 1);
        gpio_put(R_DIR, 1);

        // Normale Beschleunigung (nur wenn noch nicht in Decel-Phase)
        if (step_counter < DECEL_START) {
            if (delay_left > target_delay)  delay_left -= ramp_step;
            if (delay_right > target_delay) delay_right -= ramp_step;
        }

        // Step-Generierung 
        acc_left  += 1000.0f / delay_left;
        acc_right += 1000.0f / delay_right;

        if (acc_left >= 1.0f) {
            step_pulse(L_STEP);
            acc_left -= 1.0f;
        }

        if (acc_right >= 1.0f) {
            step_pulse(R_STEP);
            acc_right -= 1.0f;
        }

        // Zielsteps für 90°
        if (step_counter >= STEPS_FOR_90DEG) {

            // Motoren stoppen
            gpio_put(L_EN, 1);
            gpio_put(R_EN, 1);

            acc_left = acc_right = 0;

            // Geradeausrichtung wiederherstellen
            gpio_put(L_DIR, 1);
            gpio_put(R_DIR, 0);
        }

        // einfache konstante Drehgeschwindigkeit
        acc_left  += 1000.0f / 3000.0f;
        acc_right += 1000.0f / 3000.0f;

        if (acc_left >= 1.0f) {
            step_pulse(L_STEP);
            acc_left -= 1.0f;
        }
        if (acc_right >= 1.0f) {
            step_pulse(R_STEP);
            acc_right -= 1.0f;
        }
    }
    if(direction == 0)
    {
        // Sanfte Deceleration nur bei 1m-Steeckenstopp
        const uint32_t DECEL_START = STEPS_FOR_1M - 100;  // 100 Steps vorher abbremsen

        if (step_counter >= DECEL_START) {
            delay_left  += 150.0f;
            delay_right += 150.0f;

            if (delay_left > 12000.0f)  delay_left  = 12000.0f;
            if (delay_right > 12000.0f) delay_right = 12000.0f;
        }

        // Motoren sauber stoppen
        gpio_put(L_EN, 1);
        gpio_put(R_EN, 1);

        acc_left = acc_right = 0;

        step_counter = 0;

        // Drehrichtung setzen (links vorwärts, rechts rückwärts)
        gpio_put(L_DIR, 0);
        gpio_put(R_DIR, 0);

        // Normale Beschleunigung (nur wenn noch nicht in Decel-Phase)
        if (step_counter < DECEL_START) {
            if (delay_left > target_delay)  delay_left -= ramp_step;
            if (delay_right > target_delay) delay_right -= ramp_step;
        }

        // Step-Generierung 
        acc_left  += 1000.0f / delay_left;
        acc_right += 1000.0f / delay_right;

        if (acc_left >= 1.0f) {
            step_pulse(L_STEP);
            acc_left -= 1.0f;
        }

        if (acc_right >= 1.0f) {
            step_pulse(R_STEP);
            acc_right -= 1.0f;
        }
        
        // Zielsteps für 90°
        if (step_counter >= STEPS_FOR_90DEG) {

            // Motoren stoppen
            gpio_put(L_EN, 1);
            gpio_put(R_EN, 1);

            acc_left = acc_right = 0;

            // Geradeausrichtung wiederherstellen
            gpio_put(L_DIR, 1);
            gpio_put(R_DIR, 0);

        }

        // einfache konstante Drehgeschwindigkeit
        acc_left  += 1000.0f / 3000.0f;
        acc_right += 1000.0f / 3000.0f;

        if (acc_left >= 1.0f) {
            step_pulse(L_STEP);
            acc_left -= 1.0f;
        }
        if (acc_right >= 1.0f) {
            step_pulse(R_STEP);
            acc_right -= 1.0f;
        }
    }

}
    