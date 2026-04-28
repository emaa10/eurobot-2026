#include <Arduino.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"

// --- Zugschnur ---
#define PIN_PULLCORD 21

// --- Motor Pins ---
#define L_STEP 0
#define L_DIR  1
#define L_EN   7
#define R_STEP 10
#define R_DIR  9
#define R_EN   15

#define MOTORS_ON()  do { gpio_put(L_EN, 0); gpio_put(R_EN, 0); } while(0)
#define MOTORS_OFF() do { gpio_put(L_EN, 1); gpio_put(R_EN, 1); } while(0)

// --- ToF ---
#define VL53_ADDR   0x29
#define STOP_MM     500
#define RESUME_MM   540
#define BELOW_LIMIT 5

volatile bool opponent_detected = false;

// --- Fehlerwerte des VL53L0X ---
static bool tof_valid(uint16_t v) {
    return v != 0 && v != 20 && v != 8190 && v != 9999;
}

// --- Median über 3 gültige Samples ---
// Ungültige Werte werden übersprungen (Buffer bleibt unverändert)
struct MedianFilter {
    uint16_t buf[3] = {9999, 9999, 9999};
    uint8_t  idx = 0;

    void push(uint16_t v) {
        if (!tof_valid(v)) return; // Fehlerwert ignorieren
        buf[idx] = v;
        idx = (idx + 1) % 3;
    }

    uint16_t median() {
        uint16_t a = buf[0], b = buf[1], c = buf[2];
        if (a > b) { uint16_t t = a; a = b; b = t; }
        if (b > c) { uint16_t t = b; b = c; c = t; }
        if (a > b) { uint16_t t = a; a = b; b = t; }
        return b;
    }
};

static MedianFilter filter_l, filter_r;

// =============================================================
// CORE 0 — ToF Sensor
// =============================================================

static void tof_write(i2c_inst_t *i2c, uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    i2c_write_blocking(i2c, VL53_ADDR, buf, 2, false);
}

static uint16_t tof_read(i2c_inst_t *i2c) {
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

void setup() {
    Serial.begin(115200);
    sleep_ms(1500);

    i2c_init(i2c1, 100000);
    gpio_set_function(2, GPIO_FUNC_I2C); gpio_pull_up(2);
    gpio_set_function(3, GPIO_FUNC_I2C); gpio_pull_up(3);

    i2c_init(i2c0, 100000);
    gpio_set_function(12, GPIO_FUNC_I2C); gpio_pull_up(12);
    gpio_set_function(13, GPIO_FUNC_I2C); gpio_pull_up(13);

    tof_start(i2c1);
    tof_start(i2c0);

    Serial.println("Core0: ToF bereit");
}

void loop() {
    static int below = 0;

    uint16_t raw1 = tof_read(i2c1);
    uint16_t raw2 = tof_read(i2c0);

    filter_l.push(raw1);
    filter_r.push(raw2);

    uint16_t d1 = filter_l.median();
    uint16_t d2 = filter_r.median();

    // Nur zählen wenn beide Median-Werte valide sind
    bool obstacle = tof_valid(d1) && tof_valid(d2) && (d1 < STOP_MM || d2 < STOP_MM);

    if (obstacle) {
        below++;
    } else if (below > 0) {
        below--;
    }

    if (!opponent_detected && below >= BELOW_LIMIT) {
        opponent_detected = true;
        Serial.printf("[STOPP] Gegner: L=%dmm R=%dmm\n", d1, d2);
    }

    if (opponent_detected && tof_valid(d1) && tof_valid(d2) && d1 > RESUME_MM && d2 > RESUME_MM) {
        opponent_detected = false;
        below = 0;
        Serial.printf("[FREI]  L=%dmm R=%dmm\n", d1, d2);
    }

    sleep_ms(20);
}

// =============================================================
// CORE 1 — Stepper (1m vorwärts, Gegner-Stop)
// =============================================================

static inline void pulse(uint pin) {
    gpio_put(pin, 1);
    sleep_us(30);
    gpio_put(pin, 0);
}

void setup1() {
    gpio_init(L_STEP); gpio_set_dir(L_STEP, GPIO_OUT);
    gpio_init(L_DIR);  gpio_set_dir(L_DIR,  GPIO_OUT);
    gpio_init(L_EN);   gpio_set_dir(L_EN,   GPIO_OUT);
    gpio_init(R_STEP); gpio_set_dir(R_STEP, GPIO_OUT);
    gpio_init(R_DIR);  gpio_set_dir(R_DIR,  GPIO_OUT);
    gpio_init(R_EN);   gpio_set_dir(R_EN,   GPIO_OUT);
    MOTORS_OFF();

    gpio_init(PIN_PULLCORD);
    gpio_set_dir(PIN_PULLCORD, GPIO_IN);
    gpio_pull_up(PIN_PULLCORD);

    sleep_ms(2000);
    Serial.println("Core1: Stepper bereit, warte auf Zugschnur...");
    while (gpio_get(PIN_PULLCORD) == 1) sleep_ms(10);
    Serial.println("Core1: Zugschnur gezogen, starte Motor-Test");
}

void loop1() {
    gpio_put(L_DIR, 1);
    gpio_put(R_DIR, 0);
    MOTORS_ON();

    float delay_us = 6000.0f;
    const float target  = 2500.0f;
    const float ramp    = 150.0f;
    const uint32_t total = 980;

    for (uint32_t i = 0; i < total; i++) {
        if (opponent_detected) {
            MOTORS_OFF();
            while (opponent_detected) sleep_ms(10);
            MOTORS_ON();
        }

        if (i < total / 2 && delay_us > target)
            delay_us = fmaxf(delay_us - ramp, target);
        if (i > total - 100 && delay_us < 6000.0f)
            delay_us = fminf(delay_us + ramp, 6000.0f);

        pulse(L_STEP);
        pulse(R_STEP);
        sleep_us((uint32_t)delay_us);
    }

    MOTORS_OFF();
    Serial.println("1m fertig, Pause 3s");
    sleep_ms(3000);
}
