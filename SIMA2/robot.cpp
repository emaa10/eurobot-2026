#include "robot.h"
#include <Arduino.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include <math.h>

// ── Motor-Pins ────────────────────────────────────────────────
#define L_STEP  0
#define L_DIR   1
#define L_EN    7
#define R_STEP  10
#define R_DIR   9
#define R_EN    15

#define MOTORS_ON()   do { gpio_put(L_EN, 0); gpio_put(R_EN, 0); } while(0)
#define MOTORS_OFF()  do { gpio_put(L_EN, 1); gpio_put(R_EN, 1); } while(0)

// ── Kalibrierung ──────────────────────────────────────────────
// Radumfang ≈ 65 mm → 980 Steps/m (aus motor.c)
static constexpr float STEPS_PER_MM  = 980.0f / 1000.0f;
// 90° ≈ 200 Steps (aus motor.c)
static constexpr float STEPS_PER_DEG = 200.0f / 90.0f;

// Rampe
static constexpr float DELAY_START_US = 6000.0f;
static constexpr float DELAY_MIN_US   = 2500.0f;
static constexpr float RAMP_US        = 150.0f;   // Änderung pro Step

// ── ToF ───────────────────────────────────────────────────────
#define VL53_ADDR   0x29
#define STOP_MM     500
#define RESUME_MM   540
#define BELOW_LIMIT 5

volatile bool opponent_detected = false;

static bool tof_valid(uint16_t v) {
    return v != 0 && v != 20 && v != 8190 && v != 9999;
}

struct MedianFilter {
    uint16_t buf[3] = {9999, 9999, 9999};
    uint8_t  idx = 0;

    void push(uint16_t v) {
        if (!tof_valid(v)) return;
        buf[idx] = v;
        idx = (idx + 1) % 3;
    }

    uint16_t median() const {
        uint16_t a = buf[0], b = buf[1], c = buf[2];
        if (a > b) { uint16_t t = a; a = b; b = t; }
        if (b > c) { uint16_t t = b; b = c; c = t; }
        if (a > b) { uint16_t t = a; a = b; b = t; }
        return b;
    }
};

static MedianFilter filter_l, filter_r;

static void tof_write(i2c_inst_t *i2c, uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    i2c_write_blocking(i2c, VL53_ADDR, buf, 2, false);
}

static uint16_t tof_read_raw(i2c_inst_t *i2c) {
    uint8_t reg = 0x1E, buf[2] = {0xFF, 0xFF};
    if (i2c_write_blocking(i2c, VL53_ADDR, &reg, 1, true) < 0) return 9999;
    i2c_read_blocking(i2c, VL53_ADDR, buf, 2, false);
    return (buf[0] << 8) | buf[1];
}

static void tof_start(i2c_inst_t *i2c) {
    tof_write(i2c, 0x80, 0x01); tof_write(i2c, 0xFF, 0x01); tof_write(i2c, 0x00, 0x00);
    tof_write(i2c, 0x91, 0x3C); tof_write(i2c, 0x00, 0x01); tof_write(i2c, 0xFF, 0x00);
    tof_write(i2c, 0x80, 0x00); tof_write(i2c, 0x00, 0x02);
}

// ── Öffentliche Init-Funktionen ───────────────────────────────

void robotInitMotors() {
    gpio_init(L_STEP); gpio_set_dir(L_STEP, GPIO_OUT);
    gpio_init(L_DIR);  gpio_set_dir(L_DIR,  GPIO_OUT);
    gpio_init(L_EN);   gpio_set_dir(L_EN,   GPIO_OUT);
    gpio_init(R_STEP); gpio_set_dir(R_STEP, GPIO_OUT);
    gpio_init(R_DIR);  gpio_set_dir(R_DIR,  GPIO_OUT);
    gpio_init(R_EN);   gpio_set_dir(R_EN,   GPIO_OUT);
    MOTORS_OFF();
}

void robotInitTof() {
    i2c_init(i2c1, 100000);
    gpio_set_function(2, GPIO_FUNC_I2C); gpio_pull_up(2);
    gpio_set_function(3, GPIO_FUNC_I2C); gpio_pull_up(3);

    i2c_init(i2c0, 100000);
    gpio_set_function(12, GPIO_FUNC_I2C); gpio_pull_up(12);
    gpio_set_function(13, GPIO_FUNC_I2C); gpio_pull_up(13);

    tof_start(i2c1);
    tof_start(i2c0);
}

// Core0 ruft das auf (alle 20ms)
void robotPollTof() {
    static int below = 0;

    filter_l.push(tof_read_raw(i2c1));
    filter_r.push(tof_read_raw(i2c0));

    uint16_t d1 = filter_l.median();
    uint16_t d2 = filter_r.median();

    bool obstacle = tof_valid(d1) && tof_valid(d2) && (d1 < STOP_MM || d2 < STOP_MM);

    if (obstacle) { below++; } else if (below > 0) { below--; }

    if (!opponent_detected && below >= BELOW_LIMIT) {
        opponent_detected = true;
        Serial.printf("[STOPP] L=%dmm R=%dmm\n", d1, d2);
    }
    if (opponent_detected && tof_valid(d1) && tof_valid(d2) && d1 > RESUME_MM && d2 > RESUME_MM) {
        opponent_detected = false;
        below = 0;
        Serial.printf("[FREI]  L=%dmm R=%dmm\n", d1, d2);
    }
}

// ── Internes Step-Handling ────────────────────────────────────

static inline void pulse(uint pin) {
    gpio_put(pin, 1);
    sleep_us(30);
    gpio_put(pin, 0);
}

// Beide Motoren, steps Schritte, mit Rampe + Gegner-Pause
static void run_steps(uint32_t steps, bool check_opponent = true) {
    float delay_us = DELAY_START_US;
    uint32_t decel_start = steps > 80 ? steps - 80 : 0;

    for (uint32_t i = 0; i < steps; i++) {
        if (check_opponent && opponent_detected) {
            MOTORS_OFF();
            while (opponent_detected) sleep_ms(10);
            MOTORS_ON();
        }

        // Beschleunigen
        if (i < steps / 2 && delay_us > DELAY_MIN_US)
            delay_us = fmaxf(delay_us - RAMP_US, DELAY_MIN_US);
        // Abbremsen
        if (i >= decel_start && delay_us < DELAY_START_US)
            delay_us = fminf(delay_us + RAMP_US, DELAY_START_US);

        pulse(L_STEP);
        pulse(R_STEP);
        sleep_us((uint32_t)delay_us);
    }
}

// ── Öffentliche Taktik-API ────────────────────────────────────

void driveMM(int mm) {
    if (mm == 0) return;
    uint32_t steps = (uint32_t)(fabsf((float)mm) * STEPS_PER_MM);

    if (mm > 0) {
        // Vorwärts
        gpio_put(L_DIR, 1); gpio_put(R_DIR, 0);
    } else {
        // Rückwärts — Gegner-Check aus (Sensoren zeigen nach vorne)
        gpio_put(L_DIR, 0); gpio_put(R_DIR, 1);
    }

    MOTORS_ON();
    run_steps(steps, mm > 0);
    MOTORS_OFF();

    Serial.printf("[drive] %dmm (%u steps)\n", mm, steps);
}

void turnDeg(int deg) {
    if (deg == 0) return;
    uint32_t steps = (uint32_t)(fabsf((float)deg) * STEPS_PER_DEG);

    if (deg > 0) {
        // Rechts: links vorwärts, rechts rückwärts
        gpio_put(L_DIR, 1); gpio_put(R_DIR, 1);
    } else {
        // Links: links rückwärts, rechts vorwärts
        gpio_put(L_DIR, 0); gpio_put(R_DIR, 0);
    }

    MOTORS_ON();
    run_steps(steps, false); // beim Drehen kein Gegner-Check
    MOTORS_OFF();

    Serial.printf("[turn]  %ddeg (%u steps)\n", deg, steps);
}
